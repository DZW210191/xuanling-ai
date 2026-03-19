# 🧚 玄灵AI (XuanLing AI)

一个完全自研的智能体系统，基于 Python FastAPI 构建。

## ✨ 特性

- 🤖 **AI 对话** - 支持 MiniMax, OpenAI, Claude 等多种模型
- 🧠 **记忆系统** - 短期记忆 + 长期记忆，理解上下文
- 🛠️ **工具能力** - 读写文件、执行命令、浏览网页
- 🔌 **多平台插件** - 飞书、Telegram、Discord
- ⚡ **任务调度** - 定时执行任务，7×24小时工作
- 🧬 **DGM 自我改进引擎** - 持续学习和进化

## 🚀 快速开始

### 本地运行

```bash
# 克隆项目
git clone https://github.com/DZW210191/xuanling-ai.git
cd xuanling-ai

# 安装依赖
pip install -r requirements.txt

# 复制配置
cp .env.example .env
# 编辑 .env 填入 API Key

# 运行
python src/main.py
```

### Docker 部署

```bash
# 构建
docker build -t xuanling-ai .

# 运行
docker run -p 8000:8000 -e API_KEY=your_key xuanling-ai
```

或使用 docker-compose:

```bash
docker-compose up -d
```

## 📡 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页 |
| `/health` | GET | 健康检查 |
| `/chat/json` | POST | 对话 |
| `/projects` | GET/POST | 项目管理 |
| `/memory` | GET/POST | 记忆系统 |
| `/config` | GET/POST | 配置管理 |
| `/tasks` | GET/POST | 定时任务 |

## 🛠️ 可用工具

- `read` - 读取文件
- `write` - 写入文件
- `edit` - 编辑文件
- `ls` - 列出目录
- `run` - 执行命令
- `fetch` - 获取网页内容
- `github` - 获取GitHub仓库信息
- `sysinfo` - 系统信息
- `processes` - 进程列表
- `memory_search` - 搜索记忆
- `weather` - 天气查询

## 📁 项目结构

```
xuanling-ai/
├── src/
│   ├── core/       # 核心Agent
│   ├── gateway/    # 消息网关
│   ├── memory/     # 记忆系统
│   ├── model/      # 模型适配
│   ├── plugins/    # 插件
│   ├── scheduler/  # 任务调度
│   ├── skills/     # 技能
│   ├── storage/    # 存储
│   ├── tasks/      # 后台任务
│   ├── tools/      # 工具
│   └── main.py     # 主入口
├── static/         # 前端页面
├── skills/        # 技能配置
└── docker/        # Docker配置
```

## ⚙️ 配置

在 `.env` 中配置:

```bash
API_KEY=your_api_key
API_BASE_URL=https://your-api-endpoint.com/v1
```

## 📜 License

MIT

---

## 📝 更新日志

### 2026-03-20
- 技能商店: 从后端动态获取技能列表
- 本地运行: 显示实时服务状态
- 对话历史: 支持搜索、删除、清空
- 系统设置: 添加模型选择和自定义模型功能
- 项目管理: 添加查看/编辑项目文件功能
- 对话路由: 修复项目管理/记忆系统的回复内容
- 聊天记录: 刷新页面后自动恢复历史
