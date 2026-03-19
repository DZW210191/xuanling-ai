"""
任务调度器 - 定时执行任务（内置实现，无需外部依赖）
"""
import asyncio
import time
from datetime import datetime
from typing import Callable, Dict, Any, List
import threading


class Task:
    """任务"""
    
    def __init__(self, name: str, handler: Callable, interval: int = None, cron: str = None):
        self.name = name
        self.handler = handler
        self.interval = interval  # 秒
        self.cron = cron
        self.last_run = None
        self.enabled = True


class Scheduler:
    """调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self.thread = None
    
    def add_task(self, name: str, handler: Callable, interval: int = None, cron: str = None):
        """添加任务"""
        task = Task(name, handler, interval, cron)
        self.tasks[name] = task
        print(f"📅 已添加任务: {name} (间隔: {interval}秒)")
    
    def remove_task(self, name: str):
        """移除任务"""
        if name in self.tasks:
            del self.tasks[name]
            print(f"📅 已移除任务: {name}")
    
    def run_task(self, name: str):
        """手动执行任务"""
        if name in self.tasks:
            task = self.tasks[name]
            try:
                result = task.handler()
                if asyncio.iscoroutine(result):
                    asyncio.run(result)
                task.last_run = datetime.now()
                print(f"✅ 任务完成: {name}")
            except Exception as e:
                print(f"❌ 任务失败: {name} - {e}")
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        
        def run_loop():
            while self.running:
                now = datetime.now()
                
                # 检查定时任务
                for task in self.tasks.values():
                    if not task.enabled:
                        continue
                    
                    if task.interval:
                        # 间隔任务
                        if task.last_run is None or \
                           (now - task.last_run).total_seconds() >= task.interval:
                            try:
                                result = task.handler()
                                if asyncio.iscoroutine(result):
                                    asyncio.run(result)
                                task.last_run = now
                            except Exception as e:
                                print(f"❌ 任务错误: {task.name} - {e}")
                
                time.sleep(1)
        
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        print("📅 调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        print("📅 调度器已停止")
    
    def list_tasks(self) -> List[Dict]:
        """列出所有任务"""
        return [
            {
                "name": t.name,
                "interval": t.interval,
                "enabled": t.enabled,
                "last_run": t.last_run.isoformat() if t.last_run else None
            }
            for t in self.tasks.values()
        ]


# 全局调度器实例
scheduler = Scheduler()


# 预定义任务
async def check_system_health():
    """检查系统健康状态"""
    print("🔍 检查系统健康...")
    return {"status": "ok", "time": datetime.now().isoformat()}


async def cleanup_old_data():
    """清理旧数据"""
    print("🧹 清理旧数据...")


def init_default_tasks():
    """初始化默认任务"""
    scheduler.add_task("健康检查", check_system_health, interval=300)  # 5分钟
    scheduler.add_task("数据清理", cleanup_old_data, interval=3600)     # 1小时
