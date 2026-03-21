"""
玄灵AI 测试服务器 - 测试四大核心模块
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn

# 导入新模块
from tools import tool_registry
from skills import skill_manager, SkillBase, SkillMetadata, SkillConfig
from subagents import (
    task_scheduler, task_planner, SubAgent, AgentRole,
    Task, TaskStatus, TaskPriority, create_agent, submit_task
)
from memory import memory_manager, MemoryType, MemoryImportance, remember, recall
from security import permission_manager, audit_logger, Permission, Role

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("玄灵AI")

# FastAPI 应用
app = FastAPI(title="玄灵AI 测试服务器", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class MemoryRequest(BaseModel):
    content: str
    title: Optional[str] = None
    type: str = "semantic"
    importance: int = 3
    tags: List[str] = []

class TaskRequest(BaseModel):
    goal: str
    name: Optional[str] = None
    priority: str = "normal"

class SkillExecuteRequest(BaseModel):
    action: str = "execute"
    params: Dict[str, Any] = {}

# ============== Skills API ==============

@app.get("/api/skills")
def list_skills():
    """获取所有技能"""
    return {"skills": skill_manager.list_skills()}

@app.get("/api/skills/{skill_name}")
def get_skill(skill_name: str):
    """获取技能详情"""
    skill = skill_manager.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"技能不存在: {skill_name}")
    return {
        "name": skill_name,
        "metadata": skill.metadata.to_dict(),
        "handlers": list(skill._handlers.keys())
    }

@app.post("/api/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, request: SkillExecuteRequest):
    """执行技能"""
    result = await skill_manager.execute(skill_name, request.action, request.params)
    return result

# ============== SubAgents API ==============

@app.get("/api/subagents")
def list_subagents():
    """获取所有子代理"""
    stats = task_scheduler.get_stats()
    return {"agents": stats.get("agents", {})}

@app.post("/api/subagents")
async def create_subagent(name: str, role: str = "worker"):
    """创建子代理"""
    role_enum = AgentRole(role) if role in [r.value for r in AgentRole] else AgentRole.WORKER
    agent = await create_agent(name, role_enum)
    return {"success": True, "agent": agent.get_status()}

@app.get("/api/tasks")
def list_tasks(status: str = None):
    """获取任务列表"""
    task_status = TaskStatus(status) if status else None
    return {"tasks": task_scheduler.list_tasks(task_status)}

@app.get("/api/tasks/stats")
def task_stats():
    """获取任务统计"""
    return task_scheduler.get_stats()

@app.post("/api/tasks")
async def create_task(request: TaskRequest):
    """创建任务"""
    priority_map = {
        "low": TaskPriority.LOW,
        "normal": TaskPriority.NORMAL,
        "high": TaskPriority.HIGH,
        "critical": TaskPriority.CRITICAL
    }
    task_id = await submit_task(
        request.goal,
        request.name,
        priority_map.get(request.priority, TaskPriority.NORMAL)
    )
    return {"success": True, "task_id": task_id}

@app.post("/api/tasks/plan")
async def plan_tasks(goal: str):
    """规划任务"""
    tasks = await task_planner.plan(goal)
    return {"goal": goal, "tasks": [t.to_dict() for t in tasks]}

# ============== Memory API ==============

@app.get("/api/memory")
def memory_stats():
    """获取记忆统计"""
    return memory_manager.get_stats()

@app.post("/api/memory")
async def create_memory(request: MemoryRequest):
    """创建记忆"""
    mem_type = MemoryType(request.type) if request.type in [t.value for t in MemoryType] else MemoryType.SEMANTIC
    imp_enum = MemoryImportance(request.importance) if 1 <= request.importance <= 5 else MemoryImportance.NORMAL
    
    memory = await remember(
        content=request.content,
        title=request.title,
        type=mem_type,
        importance=imp_enum,
        tags=request.tags
    )
    return {"success": True, "memory": memory.to_dict()}

@app.get("/api/memory/search")
async def search_memory(query: str, top_k: int = 5):
    """搜索记忆"""
    results = await recall(query, top_k=top_k)
    return {
        "query": query,
        "results": [
            {"memory": r.memory.to_dict(), "score": r.score, "highlight": r.highlight}
            for r in results
        ]
    }

@app.get("/api/memory/working")
def working_memory():
    """获取工作记忆"""
    memories = memory_manager.get_working_memory()
    return {"memories": [m.to_dict() for m in memories]}

# ============== Security API ==============

@app.get("/api/security/users")
def list_users():
    """获取用户列表"""
    return {"users": permission_manager.list_users()}

@app.get("/api/security/api-keys")
def list_api_keys(user_id: str = None):
    """获取 API 密钥列表"""
    return {"api_keys": permission_manager.list_api_keys(user_id)}

@app.post("/api/security/api-keys")
def create_api_key(user_id: str, name: str = "API Key"):
    """创建 API 密钥"""
    try:
        api_key = permission_manager.create_api_key(user_id, name)
        return {"success": True, "key": api_key.key}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/security/audit-logs")
def audit_logs(hours: int = 24, limit: int = 100):
    """获取审计日志"""
    start_time = datetime.now() - timedelta(hours=hours)
    logs = audit_logger.query(start_time=start_time, limit=limit)
    return {"logs": [l.to_dict() for l in logs]}

@app.get("/api/security/stats")
def security_stats():
    """获取安全统计"""
    return {
        "audit": audit_logger.get_stats(),
        "users": len(permission_manager._users),
        "api_keys": len(permission_manager._api_keys)
    }

# ============== Tools API ==============

@app.get("/api/tools")
def list_tools():
    """获取所有工具"""
    tools = tool_registry.list_all()
    return {
        "tools": [
            {"name": t.name, "description": t.description, "category": t.category}
            for t in tools
        ],
        "count": len(tools)
    }

# ============== 启动事件 ==============

@app.on_event("startup")
async def startup():
    """启动时初始化"""
    logger.info("🚀 玄灵AI 测试服务器启动")
    
    # 初始化技能管理器
    skill_manager.set_tool_registry(tool_registry)
    await skill_manager.load_all()
    
    # 启动任务调度器
    await task_scheduler.start()
    
    # 创建默认代理
    try:
        await create_agent("主代理", AgentRole.WORKER)
        logger.info("✅ 默认代理已创建")
    except Exception as e:
        logger.warning(f"创建代理失败: {e}")

@app.on_event("shutdown")
async def shutdown():
    """关闭时清理"""
    await task_scheduler.stop()
    logger.info("🛑 玄灵AI 测试服务器关闭")

# ============== 健康检查 ==============

@app.get("/")
def root():
    return {"message": "玄灵AI 测试服务器", "version": "2.0.0", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    logger.info("启动玄灵AI测试服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8001)