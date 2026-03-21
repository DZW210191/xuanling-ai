# 玄灵AI 控制台 - 开发文档

## 📋 项目概述

玄灵AI 是一个基于 OpenClaw 构建的下一代 AI 代理系统，集成了 DGM 自我改进能力。

**项目地址**: `http://106.55.107.63:8080/xuanling-console.html`

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Web UI)                          │
│  xuanling-console.html (静态页面)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端 API (待开发)                       │
│  - RESTful API                                             │
│  - WebSocket 实时通信                                       │
│  - 认证鉴权                                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    核心服务层                                │
│  - OpenClaw Core                                           │
│  - DGM 自我改进引擎                                         │
│  - Skills 管理系统                                          │
│  - 记忆系统 (Memory Agent)                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据存储层                               │
│  - SQLite: 项目、任务、记忆                                  │
│  - Redis: 会话缓存、实时状态                                 │
│  - 文件系统: 配置、日志                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
xuanling-ai/
├── web/                      # 前端
│   ├── index.html           # 主控制台
│   ├── css/
│   │   └── style.css        # 样式
│   └── js/
│       └── app.js           # 前端逻辑
│
├── server/                   # 后端服务
│   ├── main.py              # FastAPI 主入口
│   ├── api/
│   │   ├── chat.py          # 对话 API
│   │   ├── projects.py      # 项目 API
│   │   ├── tasks.py         # 任务 API
│   │   ├── agents.py        # 子代理 API
│   │   ├── memory.py        # 记忆 API
│   │   └── skills.py       # Skills API
│   ├── core/
│   │   ├── openclaw.py      # OpenClaw 集成
│   │   ├── dgm.py           # DGM 引擎
│   │   └── skills.py        # Skills 管理
│   └── models/
│       └── schema.py         # 数据模型
│
├── data/                     # 数据存储
│   ├── database.db          # SQLite
│   └── logs/                # 日志
│
└── config.yaml               # 配置文件
```

---

## 🔧 后端 API 设计

### 1. 对话接口

```python
# POST /api/chat
# 请求
{
    "message": "你好",
    "project_id": 1,           # 可选，项目上下文
    "stream": false            # 是否流式响应
}

# 响应
{
    "response": "你好！有什么可以帮你的？",
    "agent": "玄灵AI",
    "timestamp": "2026-03-18T20:35:00Z",
    "memory_used": ["主人称呼偏好"]
}
```

### 2. 项目管理

```python
# GET /api/projects
# 响应
[
    {
        "id": 1,
        "name": "AI 智能代理框架",
        "description": "基于 OpenClaw 构建",
        "icon": "🤖",
        "status": "进行中",
        "progress": 65,
        "tasks": 12,
        "memory": 5,
        "created_at": "2026-03-01T00:00:00Z"
    }
]

# POST /api/projects
# 请求
{
    "name": "新项目",
    "description": "项目描述",
    "icon": "📁"
}

# GET /api/projects/{id}/memory
# 获取项目专属记忆
```

### 3. 定时任务

```python
# GET /api/tasks
[
    {
        "id": 1,
        "name": "每日早间简报",
        "schedule": "0 8 * * *",    # Cron 表达式
        "status": "running",
        "last_run": "2026-03-18T08:00:00Z",
        "next_run": "2026-03-19T08:00:00Z"
    }
]

# POST /api/tasks
{
    "name": "新任务",
    "schedule": "0 */2 * * *",
    "action": {"type": "webhook", "url": "..."}
}
```

### 4. 子代理管理

```python
# GET /api/agents
[
    {
        "id": 1,
        "name": "代码审查代理",
        "status": "running",
        "tasks_completed": 12,
        "success_rate": 0.92,
        "avg_duration": 2.3
    }
]

# POST /api/agents
{
    "name": "新代理",
    "type": "code_review",
    "config": {...}
}
```

### 5. 记忆系统

```python
# GET /api/memory
[
    {
        "id": 1,
        "title": "主人称呼偏好",
        "content": "喜欢被称呼为老板",
        "tags": ["个人"],
        "project_id": null,
        "importance": 5
    }
]

# POST /api/memory
{
    "title": "新记忆",
    "content": "记忆内容",
    "tags": ["偏好"],
    "project_id": 1
}
```

### 6. Skills 管理

```python
# GET /api/skills
# GET /api/skills/installed
# POST /api/skills/{name}/install
# POST /api/skills/{name}/uninstall
```

---

## 🎨 前端对接

### API 客户端封装

```javascript
// js/api.js
const API_BASE = '/api';

class APIClient {
    async request(endpoint, options = {}) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        return response.json();
    }

    // 对话
    chat(message, options = {}) {
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify({ message, ...options })
        });
    }

    // 项目
    getProjects() { return this.request('/projects'); }
    createProject(data) { return this.request('/projects', { method: 'POST', body: JSON.stringify(data) }); }

    // 任务
    getTasks() { return this.request('/tasks'); }

    // 代理
    getAgents() { return this.request('/agents'); }

    // 记忆
    getMemory(projectId = null) {
        const url = projectId ? `/memory?project_id=${projectId}` : '/memory';
        return this.request(url);
    }
    createMemory(data) { return this.request('/memory', { method: 'POST', body: JSON.stringify(data) }); }
}

export const api = new APIClient();
```

### 示例：加载项目列表

```javascript
// 在页面加载时获取项目
async function loadProjects() {
    try {
        const projects = await api.getProjects();
        renderProjects(projects);
    } catch (error) {
        console.error('加载项目失败:', error);
    }
}
```

---

## 🧠 DGM 自我改进集成

### 1. DGM 配置

```yaml
# config.yaml
dgm:
  enabled: true
  api_key: ${CUSTOM_API_KEY}
  api_base: ${CUSTOM_BASE_URL}
  model: MiniMax-M2.5
  auto_improve: false
  benchmark: swe_bench
```

### 2. DGM API

```python
# POST /api/dgm/improve
# 请求
{
    "target": "code_analysis",      # 改进目标
    "iterations": 10
}

# 响应
{
    "improvements": [
        {
            "iteration": 1,
            "score_before": 0.65,
            "score_after": 0.72,
            "changes": ["优化了代码审查逻辑"]
        }
    ],
    "final_score": 0.85
}
```

---

## 🗄️ 数据库设计

### 表结构 (SQLite)

```sql
-- 项目表
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT '📁',
    status TEXT DEFAULT '进行中',
    progress INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 任务表
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,
    description TEXT,
    schedule TEXT,              -- Cron 表达式
    action TEXT,                -- JSON
    status TEXT DEFAULT 'active',
    last_run DATETIME,
    next_run DATETIME
);

-- 记忆表
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    title TEXT NOT NULL,
    content TEXT,
    tags TEXT,                  -- JSON array
    importance INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 子代理表
CREATE TABLE agents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    config TEXT,                -- JSON
    status TEXT DEFAULT 'idle',
    tasks_completed INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 系统日志表
CREATE TABLE logs (
    id INTEGER PRIMARY KEY,
    level TEXT,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🚀 部署步骤

### 1. 克隆项目

```bash
git clone https://github.com/your-repo/xuanling-ai.git
cd xuanling-ai
```

### 2. 安装依赖

```bash
# Python 依赖
pip install fastapi uvicorn sqlalchemy aiosqlite redis pydantic

# 前端依赖 (可选)
npm install
```

### 3. 配置环境变量

```bash
export CUSTOM_API_KEY="your-api-key"
export CUSTOM_BASE_URL="https://your-api-endpoint.com/v1"
```

### 4. 启动服务

```bash
# 启动后端
python -m uvicorn server.main:app --reload --port 8000

# 或使用 Docker
docker-compose up -d
```

### 5. Nginx 配置 (生产环境)

```nginx
server {
    listen 80;
    server_name xuanling.ai;

    location / {
        root /var/www/xuanling-ai/web;
        index index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
}
```

---

## 📝 开发计划

### Phase 1: MVP (1周)
- [ ] 后端 API 框架搭建
- [ ] 数据库初始化
- [ ] 项目 CRUD
- [ ] 基础对话功能

### Phase 2: 核心功能 (2周)
- [ ] 定时任务系统
- [ ] 记忆系统
- [ ] Skills 管理
- [ ] 子代理框架

### Phase 3: 高级功能 (2周)
- [ ] DGM 集成
- [ ] WebSocket 实时通信
- [ ] 权限系统
- [ ] 监控面板

### Phase 4: 优化 (1周)
- [ ] 性能优化
- [ ] 安全加固
- [ ] 文档完善

---

## 🔗 相关资源

- [OpenClaw 文档](https://docs.openclaw.ai)
- [DGM Skill](./skills/dgm)
- [MiniMax API 文档](https://platform.minimax.io)

---

*最后更新: 2026-03-18*
