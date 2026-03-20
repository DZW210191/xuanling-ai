# 玄灵AI 后端

## 版本
**v1.1.0** - 增强版 (2026-03-20)

## 功能特性

| 功能 | 说明 |
|------|------|
| 🤖 AI 对话 | 支持 MiniMax API 真实对接 |
| 📁 项目管理 | CRUD 完整支持 |
| 🧠 记忆系统 | 持久化存储 |
| 📊 系统监控 | CPU/内存/任务状态 |
| 🔒 安全增强 | CORS 限制 + 异常处理 |
| 📝 日志记录 | 完整的请求日志 |

## 安装依赖

```bash
pip install fastapi uvicorn pydantic python-dotenv aiohttp
```

## 环境变量

```bash
# MiniMax API (可选，不配置则使用模拟回复)
export MINIMAX_API_KEY="your-api-key"
export MINIMAX_BASE_URL="https://api.minimax.chat/v1"

# CORS 白名单 (逗号分隔)
export CORS_ORIGINS="http://localhost:3000,http://your-domain.com"
```

## 运行服务

```bash
cd server
uvicorn main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档

---

# API 参考

## 对话

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

## 项目

```bash
# 获取项目列表
curl http://localhost:8000/api/projects

# 创建项目
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "新项目", "description": "描述", "icon": "🤖"}'

# 更新项目
curl -X PUT http://localhost:8000/api/projects/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "更新名称", "progress": 50}'

# 删除项目
curl -X DELETE http://localhost:8000/api/projects/1
```

## 记忆

```bash
# 获取记忆
curl http://localhost:8000/api/memory

# 添加记忆
curl -X POST http://localhost:8000/api/memory \
  -H "Content-Type: application/json" \
  -d '{"title": "测试", "content": "内容", "tags": ["测试"], "importance": 3}'

# 删除记忆
curl -X DELETE http://localhost:8000/api/memory/1
```

## 其他接口

```bash
# 定时任务
curl http://localhost:8000/api/tasks

# 子代理状态
curl http://localhost:8000/api/agents

# 系统监控
curl http://localhost:8000/api/monitor

# 健康检查
curl http://localhost:8000/api/health
```
