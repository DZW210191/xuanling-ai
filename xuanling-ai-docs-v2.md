# 玄灵AI - 基于 OpenClaw 深度定制

## 🎯 定位

在 OpenClaw 基础上进行深度定制，保留核心能力，增加项目管理和项目记忆功能。

---

## 🏗️ 架构设计

```
┌──────────────────────────────────────────────────────────────────┐
│                      玄灵AI Web 控制台 (自创 UI)                  │
│              xuanling-console.html                              │
└──────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                      OpenClaw Gateway (已有)                      │
│              http://localhost:11649                            │
│              • 消息路由                                         │
│              • 认证鉴权                                         │
│              • 技能编排                                         │
└──────────────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │  飞书插件    │    │  Skills     │    │  DGM        │
    │  (已有)      │    │  (已有)     │    │  (已有)     │
    └──────────────┘    └──────────────┘    └──────────────┘
                                 │
                                 ▼
                    ┌──────────────────────┐
                    │  玄灵AI 扩展层      │  ← 新增
                    │  • 项目管理        │
                    │  • 项目记忆        │
                    │  • 任务调度        │
                    └──────────────────────┘
                                 │
                                 ▼
                    ┌──────────────────────┐
                    │  存储层              │  ← 新增
                    │  • SQLite           │
                    │  • Redis (可选)     │
                    └──────────────────────┘
```

---

## 📦 与 OpenClaw 的关系

### 复用部分 (不做重复开发)

| 模块 | OpenClaw 组件 | 说明 |
|------|---------------|------|
| **核心引擎** | OpenClaw Core | 消息处理、对话管理 |
| **Skills** | ~/.openclaw/skills | 现有 2 个 + 未来扩展 |
| **飞书接入** | plugins/feishu | 已配置完成 |
| **DGM** | skills/dgm | 自我改进核心 |
| **记忆系统** | memory-agent | 全局记忆 |
| **子代理** | ACP 协议 | 并行任务 |

### 新增部分 (需要开发)

| 模块 | 说明 |
|------|------|
| **项目管理** | 项目级隔离，关联任务和记忆 |
| **项目记忆** | 按项目分类的记忆子系统 |
| **任务调度** | 基于 Cron 的定时任务 |
| **Web 控制台** | 可视化管理界面 |

---

## 🔌 集成方式

### 1. 通过 OpenClaw Skills 扩展

```python
# ~/.openclaw/skills/xuanling-project/skill.py

from openclaw import Skill, Tool

class XuanlingProjectSkill(Skill):
    """玄灵AI 项目管理 Skill"""
    
    name = "xuanling-project"
    description = "项目管理与项目记忆"
    
    tools = [
        Tool("create_project", self.create_project),
        Tool("list_projects", self.list_projects),
        Tool("add_project_memory", self.add_memory),
    ]
    
    def create_project(self, name: str, description: str = ""):
        """创建项目"""
        # 写入 SQLite
        return {"id": 1, "name": name}
    
    def list_projects(self):
        """列出所有项目"""
        return db.query("SELECT * FROM projects")
    
    def add_project_memory(self, project_id: int, content: str, tags: list):
        """添加项目记忆"""
        return {"id": 1}
```

### 2. 通过 OpenClaw API 调用

```python
# 后端通过 HTTP 调用 OpenClaw

import requests

class OpenClawClient:
    def __init__(self, token: str):
        self.base_url = "http://localhost:11649"
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def chat(self, message: str, context: dict = None):
        """发送对话"""
        return requests.post(
            f"{self.base_url}/api/chat",
            json={"message": message, "context": context},
            headers=self.headers
        )
    
    def execute_skill(self, skill_name: str, action: str, **kwargs):
        """执行 Skill"""
        return requests.post(
            f"{self.base_url}/api/skills/{skill_name}/{action}",
            json=kwargs,
            headers=self.headers
        )
```

### 3. 通过 MCP 协议 (推荐)

```json
// project-mcp-server/config.json
{
    "mcpServers": {
        "xuanling-project": {
            "command": "python",
            "args": ["/path/to/project-mcp-server.py"],
            "env": {
                "OPENCLAW_TOKEN": "your-token",
                "DATABASE_URL": "sqlite:///./xuanling.db"
            }
        }
    }
}
```

---

## 📁 扩展目录结构

```
~/.openclaw/
├── skills/
│   ├── dgm/                    # 已有
│   ├── memory-agent/            # 已有
│   └── xuanling-project/       # 新增: 项目管理
│       ├── skill.yaml
│       ├── skill.py
│       └── scripts/
│
├── extensions/
│   └── xuanling/              # 新增: 扩展目录
│       ├── __init__.py
│       ├── database.py         # SQLite 操作
│       ├── scheduler.py        # 定时任务
│       └── web_api.py         # Web API
│
└── xuanling.db                # 新增: 项目数据
```

---

## 🗄️ 数据库设计 (新增)

```sql
-- 项目表 (扩展 OpenClaw 的能力边界)
CREATE TABLE xuanling_projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT '📁',
    status TEXT DEFAULT 'active',
    progress INTEGER DEFAULT 0,
    openclaw_context TEXT,    -- JSON: 关联的对话上下文
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目记忆 (区别于全局记忆)
CREATE TABLE xuanling_project_memories (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES xuanling_projects(id),
    title TEXT NOT NULL,
    content TEXT,
    tags TEXT,                  -- JSON array
    importance INTEGER DEFAULT 1,
    source TEXT,               -- 'manual' | 'auto_extract'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目任务 (关联 Skills 执行)
CREATE TABLE xuanling_tasks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES xuanling_projects(id),
    name TEXT NOT NULL,
    description TEXT,
    schedule TEXT,             -- Cron 表达式
    skill_name TEXT,           -- 关联的 Skill
    status TEXT DEFAULT 'active',
    last_run TIMESTAMP,
    next_run TIMESTAMP
);
```

---

## 🎨 前端集成

### 调用 OpenClaw Gateway

```javascript
// web/js/xuanling.js

class XuanlingClient {
    constructor(gatewayUrl, token) {
        this.gatewayUrl = gatewayUrl;
        this.token = token;
    }
    
    // 对话 (走 OpenClaw)
    async chat(message, projectContext = null) {
        const response = await fetch(`${this.gatewayUrl}/api/chat`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message,
                project_id: projectContext?.id
            })
        });
        return response.json();
    }
    
    // 项目管理 (自建 API)
    async getProjects() {
        // 自建 API 或通过 Skill
    }
}
```

---

## 🚀 开发计划

### Phase 1: 集成 (1-2天)
- [ ] 创建 xuanling-project Skill
- [ ] 配置 MCP Server
- [ ] 打通 OpenClaw Gateway

### Phase 2: 核心功能 (3-5天)
- [ ] 项目 CRUD
- [ ] 项目记忆系统
- [ ] 任务调度

### Phase 3: 界面 (2-3天)
- [ ] Web 控制台对接
- [ ] 实时状态同步
- [ ] 项目详情页

### Phase 4: 优化 (1-2天)
- [ ] 性能优化
- [ ] 错误处理
- [ ] 文档完善

---

## 🔧 配置示例

```yaml
# ~/.openclaw/extensions/xuanling/config.yaml

xuanling:
  # OpenClaw Gateway
  gateway:
    url: http://localhost:11649
    token: ${OPENCLAW_TOKEN}
  
  # 本地存储
  database:
    path: ~/.openclaw/xuanling.db
  
  # 项目配置
  projects:
    default_icon: "📁"
    max_per_user: 50
  
  # 调度配置
  scheduler:
    enabled: true
    max_concurrent: 3
```

---

## 📝 总结

| 角色 | 职责 |
|------|------|
| **OpenClaw** | 对话、AI 能力、Skills、飞书、DGM |
| **玄灵扩展层** | 项目管理、项目记忆、定时任务 |
| **前端** | 可视化控制台 |

这样既保留 OpenClaw 全部能力，又有自己的项目管理特色！🎯
