"""
玄灵AI 子代理系统 - 真正的任务执行引擎
支持任务分解、并行执行、状态追踪、结果聚合
"""
import os
import json
import uuid
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import traceback

logger = logging.getLogger("玄灵AI.SubAgents")

# ============== 枚举定义 ==============

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

class AgentRole(Enum):
    """代理角色"""
    PLANNER = "planner"      # 规划器 - 分解任务
    WORKER = "worker"        # 执行器 - 执行子任务
    REVIEWER = "reviewer"    # 审查器 - 检查结果
    COORDINATOR = "coordinator"  # 协调器 - 聚合结果


# ============== 数据模型 ==============

@dataclass
class TaskResult:
    """任务结果"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)  # 产物文件路径

@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    parent_task_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    working_dir: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    memory: List[Dict] = field(default_factory=list)  # 任务记忆
    shared_state: Dict[str, Any] = field(default_factory=dict)  # 共享状态

@dataclass
class Task:
    """任务定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    goal: str = ""  # 任务目标
    steps: List[Dict] = field(default_factory=list)  # 执行步骤
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Optional[TaskContext] = None  # 使用 Optional，可为 None
    result: Optional[TaskResult] = None
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID
    assigned_agent: Optional[str] = None
    timeout: int = 300  # 超时秒数
    max_retries: int = 3
    retry_count: int = 0
    progress: float = 0.0  # 0.0 - 1.0
    logs: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parent_id": self.parent_id,
            "children": self.children,
            "dependencies": self.dependencies,
            "assigned_agent": self.assigned_agent,
            "progress": self.progress,
            "retry_count": self.retry_count
        }


@dataclass
class SubAgentConfig:
    """子代理配置"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    role: AgentRole = AgentRole.WORKER
    skills: List[str] = field(default_factory=list)  # 可用技能
    max_concurrent_tasks: int = 3
    timeout: int = 300
    model: str = "MiniMax-M2.5"
    system_prompt: str = ""
    tools_enabled: bool = True
    memory_enabled: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "skills": self.skills,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "model": self.model
        }


# ============== 子代理基类 ==============

class SubAgent:
    """子代理 - 执行任务的智能体"""
    
    def __init__(self, config: SubAgentConfig, engine=None, skill_manager=None):
        self.config = config
        self.engine = engine  # AI 引擎
        self.skill_manager = skill_manager
        self._current_tasks: Dict[str, Task] = {}
        self._task_history: List[str] = []
        self._state = "idle"  # idle, busy, paused
        self._lock = asyncio.Lock()
        
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def role(self) -> AgentRole:
        return self.config.role
    
    async def execute(self, task: Task) -> TaskResult:
        """执行任务"""
        async with self._lock:
            self._current_tasks[task.id] = task
            self._state = "busy"
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            # 执行任务步骤
            result = await self._execute_steps(task)
            
            task.result = result
            task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.progress = 1.0
            
            return result
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.result = TaskResult(success=False, error="任务被取消")
            return task.result
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = TaskResult(success=False, error=str(e))
            logger.error(f"任务执行失败 {task.id}: {e}", exc_info=True)
            return task.result
            
        finally:
            async with self._lock:
                if task.id in self._current_tasks:
                    del self._current_tasks[task.id]
                self._task_history.append(task.id)
                if not self._current_tasks:
                    self._state = "idle"
    
    async def _execute_steps(self, task: Task) -> TaskResult:
        """执行任务步骤"""
        results = []
        
        for i, step in enumerate(task.steps):
            step_type = step.get("type", "action")
            step_action = step.get("action", "")
            step_params = step.get("params", {})
            
            # 记录日志
            task.logs.append({
                "time": datetime.now().isoformat(),
                "step": i,
                "type": step_type,
                "action": step_action,
                "status": "started"
            })
            
            try:
                # 执行不同类型的步骤
                if step_type == "skill":
                    result = await self._execute_skill(step_action, step_params, task.context)
                elif step_type == "tool":
                    result = await self._execute_tool(step_action, step_params)
                elif step_type == "ai":
                    result = await self._execute_ai(step_action, step_params)
                elif step_type == "subtask":
                    result = await self._execute_subtask(step_action, step_params, task)
                else:
                    result = {"success": False, "error": f"未知步骤类型: {step_type}"}
                
                results.append(result)
                task.progress = (i + 1) / len(task.steps)
                
                # 步骤失败处理
                if not result.get("success"):
                    if step.get("required", True):
                        return TaskResult(
                            success=False,
                            error=f"步骤 {i} 失败: {result.get('error')}",
                            output=results
                        )
                    else:
                        logger.warning(f"可选步骤 {i} 失败: {result.get('error')}")
                
            except Exception as e:
                logger.error(f"步骤执行异常: {e}", exc_info=True)
                if step.get("required", True):
                    return TaskResult(success=False, error=str(e), output=results)
        
        return TaskResult(success=True, output=results)
    
    async def _execute_skill(self, skill_name: str, params: Dict, context: TaskContext) -> Dict:
        """执行技能"""
        if not self.skill_manager:
            return {"success": False, "error": "技能管理器未配置"}
        
        action = params.pop("action", "execute")
        return await self.skill_manager.execute(skill_name, action, params)
    
    async def _execute_tool(self, tool_name: str, params: Dict) -> Dict:
        """执行工具"""
        # 通过工具注册中心执行
        from tools import tool_registry
        return await tool_registry.execute(tool_name, params)
    
    async def _execute_ai(self, prompt: str, params: Dict) -> Dict:
        """执行 AI 推理"""
        if not self.engine:
            return {"success": False, "error": "AI 引擎未配置"}
        
        result = await self.engine.chat_simple(prompt)
        return {"success": True, "output": result}
    
    async def _execute_subtask(self, task_def: Dict, params: Dict, parent_task: Task) -> Dict:
        """执行子任务"""
        # 创建子任务
        subtask = Task(
            name=task_def.get("name", "子任务"),
            description=task_def.get("description", ""),
            goal=task_def.get("goal", ""),
            steps=task_def.get("steps", []),
            parent_id=parent_task.id,
            context=parent_task.context,
            priority=parent_task.priority
        )
        
        parent_task.children.append(subtask.id)
        
        # 递归执行
        result = await self.execute(subtask)
        
        return {
            "success": result.success,
            "subtask_id": subtask.id,
            "output": result.output,
            "error": result.error
        }
    
    def pause(self):
        """暂停代理"""
        self._state = "paused"
    
    def resume(self):
        """恢复代理"""
        self._state = "idle" if not self._current_tasks else "busy"
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "state": self._state,
            "current_tasks": len(self._current_tasks),
            "task_history": len(self._task_history)
        }


# ============== 任务调度器 ==============

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self._task_queue: asyncio.PriorityQueue = None
        self._tasks: Dict[str, Task] = {}
        self._agents: Dict[str, SubAgent] = {}
        self._running = False
        self._worker_task: asyncio.Task = None
        self._lock = asyncio.Lock()
        
    async def start(self):
        """启动调度器"""
        self._task_queue = asyncio.PriorityQueue()
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"🚀 任务调度器启动，最大工作线程: {self.max_workers}")
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 任务调度器停止")
    
    def register_agent(self, agent: SubAgent):
        """注册代理"""
        self._agents[agent.id] = agent
        logger.info(f"📝 注册代理: {agent.name} ({agent.role.value})")
    
    def unregister_agent(self, agent_id: str):
        """注销代理"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"🗑️ 注销代理: {agent_id}")
    
    async def submit(self, task: Task) -> str:
        """提交任务"""
        # 确保调度器已启动
        if self._task_queue is None:
            await self.start()
        
        async with self._lock:
            self._tasks[task.id] = task
        
        # 按优先级入队（优先级值越大越先执行）
        await self._task_queue.put((-task.priority.value, task.created_at, task.id))
        
        logger.info(f"📥 提交任务: {task.name} (ID: {task.id}, 优先级: {task.priority.name})")
        return task.id
    
    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            
            task.status = TaskStatus.CANCELLED
            return True
    
    async def _worker_loop(self):
        """工作循环"""
        workers = []
        
        while self._running:
            try:
                # 获取任务
                _, _, task_id = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                
                task = self._tasks.get(task_id)
                if not task or task.status == TaskStatus.CANCELLED:
                    continue
                
                # 选择代理
                agent = await self._select_agent(task)
                if not agent:
                    # 没有可用代理，重新入队
                    await self._task_queue.put((-task.priority.value, task.created_at, task.id))
                    await asyncio.sleep(0.5)
                    continue
                
                # 启动执行
                worker = asyncio.create_task(self._execute_with_agent(agent, task))
                workers.append(worker)
                
                # 清理已完成的 workers
                workers = [w for w in workers if not w.done()]
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"工作循环异常: {e}", exc_info=True)
        
        # 等待所有 workers 完成
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
    
    async def _select_agent(self, task: Task) -> Optional[SubAgent]:
        """选择合适的代理执行任务"""
        # 简单轮询策略
        for agent in self._agents.values():
            if agent._state == "idle":
                return agent
        return None
    
    async def _execute_with_agent(self, agent: SubAgent, task: Task):
        """用指定代理执行任务"""
        try:
            result = await asyncio.wait_for(
                agent.execute(task),
                timeout=task.timeout
            )
            logger.info(f"✅ 任务完成: {task.name} (ID: {task.id})")
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.result = TaskResult(success=False, error="任务超时")
            logger.error(f"⏱️ 任务超时: {task.name} (ID: {task.id})")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = TaskResult(success=False, error=str(e))
            logger.error(f"❌ 任务失败: {task.name} (ID: {task.id}): {e}")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def list_tasks(self, status: TaskStatus = None) -> List[Dict]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]
    
    def get_stats(self) -> Dict:
        """获取统计"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = len([t for t in self._tasks.values() if t.status == status])
        
        return {
            "total_tasks": len(self._tasks),
            "status_counts": status_counts,
            "agents": {aid: agent.get_status() for aid, agent in self._agents.items()},
            "running": self._running
        }


# ============== 任务规划器 ==============

class TaskPlanner:
    """任务规划器 - 将复杂目标分解为任务"""
    
    def __init__(self, engine=None):
        self.engine = engine
    
    async def plan(self, goal: str, context: TaskContext = None) -> List[Task]:
        """
        规划任务
        
        Args:
            goal: 目标描述
            context: 任务上下文
        
        Returns:
            任务列表（可能有依赖关系）
        """
        # 使用 AI 进行规划
        if self.engine:
            plan_prompt = f"""请将以下目标分解为具体的执行步骤：

目标: {goal}

请输出 JSON 格式的任务列表，每个任务包含:
- name: 任务名称
- description: 任务描述
- steps: 执行步骤列表，每个步骤包含 type(action/skill/tool/ai), action, params
- priority: 优先级 (low/normal/high/critical)
- dependencies: 依赖的任务索引（可选）

输出格式:
{{
  "tasks": [
    {{
      "name": "任务名称",
      "description": "描述",
      "steps": [
        {{"type": "tool", "action": "read_file", "params": {{"path": "/some/path"}}}}
      ],
      "priority": "normal"
    }}
  ]
}}
"""
            result = await self.engine.chat_simple(plan_prompt)
            
            # 解析 AI 输出
            tasks = self._parse_plan(result, goal, context)
            if tasks:
                return tasks
        
        # 默认规划：创建单一任务
        return [Task(
            name=goal[:50],
            description=goal,
            goal=goal,
            steps=[{"type": "ai", "action": goal, "params": {}}],
            context=context
        )]
    
    def _parse_plan(self, ai_output: str, goal: str, context: TaskContext) -> Optional[List[Task]]:
        """解析 AI 规划输出"""
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', ai_output)
            if not json_match:
                return None
            
            plan = json.loads(json_match.group())
            tasks = []
            
            priority_map = {
                "low": TaskPriority.LOW,
                "normal": TaskPriority.NORMAL,
                "high": TaskPriority.HIGH,
                "critical": TaskPriority.CRITICAL
            }
            
            for i, task_def in enumerate(plan.get("tasks", [])):
                # 处理依赖
                deps = task_def.get("dependencies", [])
                dep_ids = [tasks[d]["id"] for d in deps if d < len(tasks)]
                
                task = Task(
                    name=task_def.get("name", f"任务{i+1}"),
                    description=task_def.get("description", ""),
                    goal=task_def.get("description", ""),
                    steps=task_def.get("steps", []),
                    priority=priority_map.get(task_def.get("priority", "normal"), TaskPriority.NORMAL),
                    dependencies=dep_ids,
                    context=context
                )
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            logger.error(f"解析任务规划失败: {e}")
            return None


# ============== 全局实例 ==============

task_scheduler = TaskScheduler()
task_planner = TaskPlanner()


# ============== 便捷函数 ==============

async def create_agent(
    name: str,
    role: AgentRole = AgentRole.WORKER,
    skills: List[str] = None,
    **kwargs
) -> SubAgent:
    """创建子代理"""
    config = SubAgentConfig(
        name=name,
        role=role,
        skills=skills or [],
        **kwargs
    )
    
    # 导入引擎和技能管理器
    from engine import ai_engine
    from skills import skill_manager
    
    agent = SubAgent(config, ai_engine, skill_manager)
    task_scheduler.register_agent(agent)
    
    return agent


async def submit_task(
    goal: str,
    name: str = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    steps: List[Dict] = None,
    context: TaskContext = None
) -> str:
    """提交任务"""
    task = Task(
        name=name or goal[:50],
        description=goal,
        goal=goal,
        steps=steps or [],
        priority=priority,
        context=context
    )
    
    return await task_scheduler.submit(task)


async def plan_and_execute(goal: str, context: TaskContext = None) -> List[TaskResult]:
    """规划并执行任务"""
    # 规划
    tasks = await task_planner.plan(goal, context)
    
    # 提交所有任务
    for task in tasks:
        await task_scheduler.submit(task)
    
    # 等待所有任务完成
    results = []
    for task in tasks:
        while task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            await asyncio.sleep(0.5)
        results.append(task.result)
    
    return results