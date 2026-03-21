# 玄灵AI - 架构参考与创新扩展

## 📊 OpenClaw 核心架构分析

### OpenClaw 现有架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenClaw Gateway (11649)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Router   │  │  Session   │  │   Auth    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
            │                 │                │
            ▼                 ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Runtime                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Model    │  │   Memory   │  │   Tools    │            │
│  │ (MiniMax)  │  │ (Context)  │  │  (Skills)  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
            │                 │                │
            ▼                 ▼                ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  飞书   │  │ Telegram │  │ Discord │  │  Skills │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
```

---

## 🧬 玄灵AI - 架构创新扩展

### 整体架构 (参考 + 创新)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         玄灵AI Gateway (自研)                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Router (扩展)                              │   │
│  │   • 项目路由                                                   │   │
│  │   • 意图识别                                                   │   │
│  │   • 上下文注入                                                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  OpenClaw    │    │  玄灵扩展层  │    │  第三方服务  │
│   Core       │    │   (自研)    │    │              │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ • 对话引擎    │    │ • 项目管理   │    │ • 飞书 API   │
│ • Skills    │    │ • 项目记忆   │    │ • MiniMax   │
│ • DGM      │    │ • 任务调度   │    │ • DGM API   │
│ • ACP      │    │ • 工作流     │    │              │
│ • MCP      │    │ • 监控系统   │    │              │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
                    ┌───────────────────────┐
                    │    数据存储层          │
                    ├───────────────────────┤
                    │  SQLite: 项目/任务   │
                    │  Redis: 缓存/会话    │
                    │  Files: 配置/日志    │
                    └───────────────────────┘
```

---

## 🔬 核心创新模块

### 1. 项目管理系统 (自研)

```python
# xuanling/core/projects.py

from datetime import datetime
from typing import List, Optional
import sqlite3

class Project:
    """项目核心类"""
    
    def __init__(self, id: int, name: str, description: str = "", icon: str = "📁"):
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.status = "进行中"
        self.progress = 0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def update_progress(self, progress: int):
        """更新进度"""
        self.progress = min(100, max(0, progress))
        self.updated_at = datetime.now()
    
    def complete(self):
        """完成项目"""
        self.status = "已完成"
        self.progress = 100
        self.updated_at = datetime.now()


class ProjectManager:
    """项目管理器"""
    
    def __init__(self, db_path: str = "xuanling.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '📁',
                status TEXT DEFAULT '进行中',
                progress INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def create_project(self, name: str, description: str = "", icon: str = "📁") -> Project:
        """创建项目"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, description, icon) VALUES (?, ?, ?)",
            (name, description, icon)
        )
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return Project(project_id, name, description, icon)
    
    def get_projects(self) -> List[Project]:
        """获取所有项目"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [Project(r["id"], r["name"], r["description"], r["icon"]) for r in rows]
```

### 2. 项目记忆系统 (创新)

```python
# xuanling/core/memory.py

from datetime import datetime
from typing import List, Dict, Any
import sqlite3
import json

class ProjectMemory:
    """项目记忆 - 区别于全局记忆"""
    
    TAGS = ["个人", "偏好", "重要", "技术", "业务"]
    
    def __init__(self, id: int, project_id: int, title: str, content: str, 
                 tags: List[str], importance: int = 1):
        self.id = id
        self.project_id = project_id
        self.title = title
        self.content = content
        self.tags = tags
        self.importance = importance
        self.created_at = datetime.now()


class ProjectMemoryManager:
    """项目记忆管理器"""
    
    def __init__(self, db_path: str = "xuanling.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_memories (
                id INTEGER PRIMARY KEY,
                project_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                importance INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        conn.commit()
        conn.close()
    
    def add_memory(self, project_id: int, title: str, content: str, 
                   tags: List[str], importance: int = 1) -> ProjectMemory:
        """添加项目记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO project_memories (project_id, title, content, tags, importance) VALUES (?, ?, ?, ?, ?)",
            (project_id, title, content, json.dumps(tags), importance)
        )
        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ProjectMemory(memory_id, project_id, title, content, tags, importance)
    
    def get_project_memories(self, project_id: int) -> List[ProjectMemory]:
        """获取项目所有记忆"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM project_memories WHERE project_id = ? ORDER BY importance DESC",
            (project_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            ProjectMemory(r["id"], r["project_id"], r["title"], r["content"], 
                        json.loads(r["tags"]), r["importance"])
            for r in rows
        ]
    
    def search_memories(self, query: str) -> List[ProjectMemory]:
        """搜索记忆"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM project_memories WHERE title LIKE ? OR content LIKE ?",
            (f"%{query}%", f"%{query}%")
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            ProjectMemory(r["id"], r["project_id"], r["title"], r["content"],
                        json.loads(r["tags"]), r["importance"])
            for r in rows
        ]
```

### 3. 智能任务调度 (创新)

```python
# xuanling/core/scheduler.py

from datetime import datetime, timedelta
from typing import Callable, Dict, Any
import threading
import time
import croniter

class ScheduledTask:
    """定时任务"""
    
    def __init__(self, id: int, name: str, schedule: str, 
                 handler: Callable, kwargs: Dict[str, Any]):
        self.id = id
        self.name = name
        self.schedule = schedule  # Cron 表达式
        self.handler = handler
        self.kwargs = kwargs
        self.last_run = None
        self.next_run = None
        self.status = "active"
    
    def should_run(self) -> bool:
        """检查是否应该执行"""
        if self.status != "active":
            return False
        if self.next_run is None:
            return True
        return datetime.now() >= self.next_run
    
    def calculate_next_run(self):
        """计算下次执行时间"""
        if self.schedule:
            cron = croniter.croniter(self.schedule, datetime.now())
            self.next_run = cron.get_next(datetime)
        else:
            self.next_run = None


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[int, ScheduledTask] = {}
        self.running = False
        self.thread = None
    
    def add_task(self, name: str, schedule: str, handler: Callable, 
                **kwargs) -> ScheduledTask:
        """添加任务"""
        task_id = len(self.tasks) + 1
        task = ScheduledTask(task_id, name, schedule, handler, kwargs)
        task.calculate_next_run()
        self.tasks[task_id] = task
        return task
    
    def start(self):
        """启动调度器"""
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def _run_loop(self):
        """调度循环"""
        while self.running:
            for task in self.tasks.values():
                if task.should_run():
                    try:
                        task.handler(**task.kwargs)
                        task.last_run = datetime.now()
                        task.calculate_next_run()
                    except Exception as e:
                        print(f"Task {task.name} failed: {e}")
            time.sleep(10)  # 每10秒检查一次
    
    def stop(self):
        """停止调度器"""
        self.running = False
```

### 4. 工作流引擎 (创新)

```python
# xuanling/core/workflow.py

from typing import List, Dict, Any, Callable
from enum import Enum

class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowNode:
    """工作流节点"""
    
    def __init__(self, id: str, name: str, handler: Callable):
        self.id = id
        self.name = name
        self.handler = handler
        self.inputs = {}
        self.output = None
    
    def execute(self, context: Dict[str, Any]) -> Any:
        """执行节点"""
        self.output = self.handler(context, self.inputs)
        return self.output


class Workflow:
    """工作流"""
    
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
        self.nodes: List[WorkflowNode] = []
        self.edges: Dict[str, str] = {}  # node_id -> next_node_id
        self.status = WorkflowStatus.PENDING
        self.context = {}
    
    def add_node(self, node_id: str, name: str, handler: Callable) -> WorkflowNode:
        """添加节点"""
        node = WorkflowNode(node_id, name, handler)
        self.nodes.append(node)
        return node
    
    def add_edge(self, from_node: str, to_node: str):
        """添加边"""
        self.edges[from_node] = to_node
    
    def execute(self) -> Dict[str, Any]:
        """执行工作流"""
        self.status = WorkflowStatus.RUNNING
        
        node_map = {n.id: n for n in self.nodes}
        current = self.nodes[0] if self.nodes else None
        
        while current:
            try:
                current.execute(self.context)
                self.context[current.id] = current.output
                
                next_id = self.edges.get(current.id)
                if next_id and next_id in node_map:
                    current = node_map[next_id]
                else:
                    break
            except Exception as e:
                self.status = WorkflowStatus.FAILED
                return {"error": str(e)}
        
        self.status = WorkflowStatus.COMPLETED
        return self.context
```

---

## 📦 模块依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                    表现层 (Web UI)                       │
│         xuanling-console.html (现有)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (自研)                      │
│              FastAPI + WebSocket                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ 项目路由    │  │ 记忆路由    │  │ 任务路由    │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  项目管理     │    │  项目记忆     │    │  任务调度    │
│  Project     │    │  Memory      │    │  Scheduler  │
│  Manager     │    │  Manager     │    │              │
└───────────────┘    └───────────────┘    └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                ┌───────────────────────┐
                │    SQLite 数据库        │
                │  • projects          │
                │  • project_memories  │
                │  • tasks            │
                │  • workflows        │
                └───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   OpenClaw Gateway    │
                │   (对话/AI/Skills)   │
                └───────────────────────┘
```

---

## 🚀 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/xuanling-ai.git
cd xuanling-ai

# 2. 安装依赖
pip install fastapi uvicorn sqlalchemy aiosqlite croniter

# 3. 启动服务
python -m xuanling.server.main

# 4. 访问
# Web UI: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

---

*架构设计完成，接下来可以开始编码实现！*
