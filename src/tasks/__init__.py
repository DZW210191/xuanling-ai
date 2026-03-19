"""
后台任务系统 - 执行长时间运行的任务
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundTask:
    """后台任务"""
    
    def __init__(self, task_id: str, name: str, handler: Callable, args=(), kwargs=None):
        self.id = task_id
        self.name = name
        self.handler = handler
        self.args = args
        self.kwargs = kwargs or {}
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
    
    async def run(self):
        """执行任务"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        
        try:
            if asyncio.iscoroutinefunction(self.handler):
                self.result = await self.handler(*self.args, **self.kwargs)
            else:
                self.result = self.handler(*self.args, **self.kwargs)
            self.status = TaskStatus.COMPLETED
        except Exception as e:
            self.error = str(e)
            self.status = TaskStatus.FAILED
        finally:
            self.completed_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.tasks: Dict[str, BackgroundTask] = {}
        self.max_tasks = 100  # 最多保留100个任务
    
    def create_task(self, name: str, handler: Callable, *args, **kwargs) -> str:
        """创建后台任务"""
        task_id = str(uuid.uuid4())[:8]
        task = BackgroundTask(task_id, name, handler, args, kwargs)
        self.tasks[task_id] = task
        
        # 启动任务
        asyncio.create_task(task.run())
        
        # 清理旧任务
        self._cleanup()
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def list_tasks(self) -> list:
        """列出所有任务"""
        return [t.to_dict() for t in self.tasks.values()]
    
    def _cleanup(self):
        """清理已完成的任务"""
        if len(self.tasks) > self.max_tasks:
            # 删除最旧的任务
            sorted_tasks = sorted(self.tasks.items(), key=lambda x: x[1].created_at)
            for task_id, _ in sorted_tasks[:len(self.tasks) - self.max_tasks]:
                del self.tasks[task_id]


# 全局任务管理器
task_manager = TaskManager()
