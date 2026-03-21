# 核心知识库 (永久保存)

## 关于主人

- **称呼**: 亲爱的 / 主人 / 老板
- **ID**: ou_53de6041915e2359853ce25a9fac9361
- **平台**: 飞书
- **服务器**: 腾讯云 CVM
- **偏好**: 最喜欢蓝色、喜欢跑步

## 关于我 (灵薇)

- **名字**: 灵薇
- **身份**: AI 助手 (OpenClaw)
- **核心技能**: DGM (Darwin Gödel Machine)
- **API**: MiniMax-M2.5

## 玄灵AI 项目

- **项目名**: xuanling-ai
- **位置**: /root/.openclaw/workspace/xuanling-ai
- **GitHub仓库**: https://github.com/DZW210191/xuanling-ai.git
- **Token**: REDACTED (已配置)
- **推送规则**: 
  - 代码更新**及时推送**
  - **不推送** API Key、config.yaml、.env、*.db 等敏感文件
  - 使用 .gitignore 过滤敏感文件

---

## 玄灵AI 核心架构 (2026-03-21 完成)

```
server/
├── main.py              # FastAPI 主入口 (端口 8000)
├── static/index.html    # 前端界面
├── tools/__init__.py    # 工具注册中心
├── engine/__init__.py   # AI 对话引擎
│
├── skills/              # 🛠️ Skills 技能系统
│   ├── __init__.py      # SkillBase, SkillManager, 热重载
│   └── file_ops.py      # 文件操作技能示例 (read/write/list/search/delete/mkdir)
│
├── subagents/           # 🤖 子代理执行引擎
│   └── __init__.py      # SubAgent, TaskScheduler, TaskPlanner
│                       # 角色类型: WORKER, PLANNER, REVIEWER, COORDINATOR
│
├── memory/              # 🧠 记忆系统
│   └── __init__.py      # MemoryManager, EmbeddingEngine, VectorStore
│                       # 记忆类型: EPISODIC, SEMANTIC, PROCEDURAL, WORKING
│
├── security/            # 🔐 安全系统
│   └── __init__.py      # PermissionManager, AuditLogger, RateLimiter
│                       # 角色: ADMIN, USER, GUEST, AGENT, SERVICE
│
├── project_manager/     # 📁 项目管理模块
│   └── __init__.py      # ProjectManager, TaskParser
│                       # 功能: 文字下达任务、文档上传、智能解析
│
├── projects/            # 项目数据存储
└── uploads/             # 上传文件存储
```

---

## API 端点汇总

### 项目管理 API
| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/projects` | GET | 项目列表 |
| `/api/projects` | POST | 创建项目 |
| `/api/projects/{id}` | GET | 项目详情 |
| `/api/projects/{id}/tasks/parse-text` | POST | 📝 文字下达任务 |
| `/api/projects/{id}/documents` | POST | 📄 上传文档 |
| `/api/documents/{id}/parse` | POST | 📋 解析文档生成任务 |

### Skills API
| 端点 | 功能 |
|------|------|
| `GET /api/skills` | 技能列表 |
| `POST /api/skills/{name}/execute` | 执行技能 |

### SubAgents API
| 端点 | 功能 |
|------|------|
| `GET /api/subagents` | 代理列表 |
| `POST /api/subagents` | 创建代理 |
| `GET /api/tasks/stats` | 任务统计 |

### Memory API
| 端点 | 功能 |
|------|------|
| `GET /api/memory` | 记忆统计 |
| `POST /api/memory` | 创建记忆 |
| `GET /api/memory/search` | 语义搜索 |

### Security API
| 端点 | 功能 |
|------|------|
| `GET /api/security/stats` | 安全统计 |
| `POST /api/security/api-keys` | 创建API密钥 |
| `GET /api/security/audit-logs` | 审计日志 |

---

## 开发日志

### 2026-03-21 (重要性: 5/5)

**上午 - 四大核心模块开发**

1. **Skills 系统** (`skills/__init__.py`)
   - SkillBase 基类、SkillManager 管理器
   - 热加载、依赖管理、生命周期
   - 自动注册工具到 tool_registry
   - 修复: register_handler bug (handler 未存储)

2. **子代理执行** (`subagents/__init__.py`)
   - SubAgent, TaskScheduler, TaskPlanner
   - 任务优先级、依赖管理、并行执行
   - 多角色: WORKER, PLANNER, REVIEWER, COORDINATOR

3. **记忆系统** (`memory/__init__.py`)
   - MemoryManager, EmbeddingEngine, VectorStore
   - 向量维度: 1536
   - 记忆衰减、访问强化、重要性权重

4. **安全系统** (`security/__init__.py`)
   - PermissionManager (RBAC)
   - AuditLogger, RateLimiter
   - 默认管理员: admin

**下午 - 项目管理模块**

5. **项目管理** (`project_manager/__init__.py`)
   - Project, ProjectTask, ProjectDocument
   - TaskParser: 从文字/文档解析任务
   - 智能识别"紧急"、"优先"关键词

6. **前端界面** (`static/index.html`)
   - 项目列表和详情页
   - 📝 文字下达任务输入框
   - 📄 文档上传区域
   - 📋 任务列表（状态筛选）
   - 📚 文档列表（解析/下载）

**修复的问题**
- 删除重复路由 `/api/memory`, `/api/tasks`, `/api/skills`
- 修复函数名冲突 `create_agent` → `create_subagent`
- 修正路由顺序 `/api/tasks/stats` 优先
- 安装 python-multipart 支持文件上传

---

_Last updated: 2026-03-21 14:35 | 重要性: 5_
