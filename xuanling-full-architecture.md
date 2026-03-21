# 玄灵AI - 完全自研智能体系统

## 🎯 目标

从零搭建一个完整的 AI Agent 系统，类似 OpenClaw 但完全自主研发。

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      客户端层 (Clients)                            │
│   飞书 │ Telegram │ Discord │ Web │ WhatsApp │ ...              │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      网关层 (Gateway) - 自研                      │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   Router   │  │   Auth     │  │   Rate    │            │
│   │   消息路由  │  │   认证鉴权  │  │   限流    │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      核心层 (Core) - 自研                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   Agent    │  │   Memory   │  │   Skills   │            │
│   │   代理核心  │  │   记忆系统  │  │   技能系统  │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   Tools    │  │  Scheduler │  │    DGM    │            │
│   │   工具箱   │  │   调度器   │  │  自我改进  │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      模型层 (Model) - 可替换                        │
│   MiniMax │ OpenAI │ Claude │ 智谱 │ 通义 │ ...                   │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      存储层 (Storage)                               │
│   SQLite │ Redis │ 文件系统                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
xuanling/
├── src/
│   ├── __init__.py
│   ├── main.py                 # 入口
│   │
│   ├── gateway/               # 网关层
│   │   ├── __init__.py
│   │   ├── router.py         # 消息路由
│   │   ├── auth.py           # 认证
│   │   ├── rate_limit.py     # 限流
│   │   └── ws.py             # WebSocket
│   │
│   ├── core/                  # 核心层
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent 核心
│   │   ├── session.py        # 会话管理
│   │   ├── context.py        # 上下文
│   │   └── config.py        # 配置
│   │
│   ├── memory/               # 记忆系统
│   │   ├── __init__.py
│   │   ├── short_term.py    # 短期记忆
│   │   ├── long_term.py     # 长期记忆
│   │   └── vector.py        # 向量存储
│   │
│   ├── skills/               # 技能系统
│   │   ├── __init__.py
│   │   ├── loader.py        # 加载器
│   │   ├── registry.py      # 注册表
│   │   └── executor.py      # 执行器
│   │
│   ├── tools/                # 工具箱
│   │   ├── __init__.py
│   │   ├── registry.py      # 工具注册
│   │   └── base.py         # 基础工具
│   │
│   ├── scheduler/            # 任务调度
│   │   ├── __init__.py
│   │   ├── cron.py          # Cron 调度
│   │   └── tasks.py        # 任务管理
│   │
│   ├── dgm/                 # 自我改进 (参考 DGM 设计)
│   │   ├── __init__.py
│   │   ├── engine.py        # DGM 引擎
│   │   └── benchmark.py    # 基准测试
│   │
│   ├── model/               # 模型适配
│   │   ├── __init__.py
│   │   ├── base.py         # 基础类
│   │   ├── minimax.py      # MiniMax
│   │   ├── openai.py       # OpenAI
│   │   └── router.py        # 路由
│   │
│   ├── plugins/              # 插件系统
│   │   ├── __init__.py
│   │   ├── base.py         # 基础插件
│   │   ├── feishu.py       # 飞书
│   │   ├── telegram.py      # Telegram
│   │   └── discord.py      # Discord
│   │
│   └── storage/              # 存储层
│       ├── __init__.py
│       ├── database.py       # SQLite
│       └── cache.py         # Redis
│
├── skills/                    # 技能包
│   ├── skill.yaml
│   └── handler.py
│
├── tests/                    # 测试
│
├── config.yaml               # 配置文件
├── requirements.txt          # 依赖
└── README.md
```

---

## 🔑 核心模块详解

### 1. Gateway - 消息网关

```python
# src/gateway/router.py

from typing import Dict, Any, Callable
from dataclasses import dataclass
import asyncio

@dataclass
class Message:
    """消息结构"""
    id: str
    sender: str
    content: str
    platform: str
    channel: str
    metadata: Dict[str, Any]
    timestamp: float

class Router:
    """消息路由器"""
    
    def __init__(self):
        self.routes: Dict[str, Callable] = {}
        self.middlewares: list = []
    
    def route(self, pattern: str):
        """路由装饰器"""
        def decorator(func):
            self.routes[pattern] = func
            return func
        return decorator
    
    async def handle(self, message: Message) -> str:
        """处理消息"""
        # 1. 限流检查
        if not await self.rate_limit.check(message.sender):
            return "请求过于频繁，请稍后再试"
        
        # 2. 认证检查
        if not await self.auth.verify(message):
            return "认证失败"
        
        # 3. 路由匹配
        for pattern, handler in self.routes.items():
            if self.match(pattern, message.content):
                return await handler(message)
        
        # 4. 默认处理器
        return await self.default_handler(message)
    
    async def default_handler(self, message: Message) -> str:
        """默认处理 - 走 Agent"""
        response = await self.agent.process(message)
        return response
```

### 2. Agent - 核心代理

```python
# src/core/agent.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

@dataclass
class Turn:
    """对话轮次"""
    user: str
    assistant: str
    tools_used: List[str]
    timestamp: float

class Agent:
    """AI 代理核心"""
    
    def __init__(self, config: Dict[str, Any]):
        self.name = config["name"]
        self.model = config["model"]
        self.model_client = self._init_model(config["model"])
        self.memory = MemoryManager(config.get("memory", {}))
        self.tools = ToolRegistry()
        self.skills = SkillRegistry()
        self.session_id = None
    
    async def process(self, message: str, context: Dict = None) -> str:
        """处理消息"""
        # 1. 构建上下文
        ctx = await self._build_context(message, context)
        
        # 2. 构建 Prompt
        prompt = self._build_prompt(ctx)
        
        # 3. 调用模型
        response = await self.model_client.chat(prompt)
        
        # 4. 提取工具调用
        if self._should_use_tools(response):
            tool_calls = self._extract_tools(response)
            for tool in tool_calls:
                result = await self.tools.execute(tool)
                # 追加工具结果到上下文
                ctx["tool_results"] = result
                # 重新调用模型
                response = await self.model_client.chat(self._build_prompt(ctx))
        
        # 5. 保存到记忆
        await self.memory.add_turn(message, response)
        
        return response
    
    async def _build_context(self, message: str, context: Dict = None) -> Dict:
        """构建上下文"""
        ctx = {
            "message": message,
            "history": await self.memory.get_recent(10),
            "system": self.system_prompt,
        }
        if context:
            ctx.update(context)
        return ctx
```

### 3. Memory - 记忆系统

```python
# src/memory/manager.py

from typing import List, Dict, Any
from dataclasses import dataclass
import time

@dataclass
class MemoryItem:
    """记忆项"""
    id: str
    content: str
    type: str  # "short_term" | "long_term" | "important"
    embedding: List[float]
    tags: List[str]
    created_at: float
    access_count: int = 0

class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, config: Dict):
        self.short_term_limit = config.get("short_term_limit", 20)
        self.vector_store = VectorStore(config.get("vector_dim", 1536))
        self.storage = MemoryStorage()
    
    async def add_turn(self, user_msg: str, assistant_msg: str):
        """添加对话轮次"""
        # 短期记忆
        item = MemoryItem(
            id=self._gen_id(),
            content=f"用户: {user_msg}\n助手: {assistant_msg}",
            type="short_term",
            embedding=await self._embed(f"{user_msg} {assistant_msg}"),
            tags=[],
            created_at=time.time()
        )
        await self.storage.save(item)
    
    async def get_recent(self, limit: int = 10) -> List[str]:
        """获取最近记忆"""
        items = await self.storage.get_recent(limit)
        return [f"用户: {i.content.split('\n')[0]}\n{i.content.split('\n')[1]}" for i in items]
    
    async def search(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """语义搜索"""
        query_emb = await self._embed(query)
        return await self.vector_store.search(query_emb, limit)
```

### 4. Skills - 技能系统

```python
# src/skills/registry.py

from typing import Dict, Any, Callable
from dataclasses import dataclass
import yaml

@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    version: str
    tools: list
    handler: Callable

class SkillRegistry:
    """技能注册表"""
    
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.loader = SkillLoader()
    
    def register(self, skill: Skill):
        """注册技能"""
        self.skills[skill.name] = skill
    
    async def execute(self, skill_name: str, action: str, **kwargs) -> Any:
        """执行技能"""
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill {skill_name} not found")
        
        handler = getattr(skill.handler, action, None)
        if not handler:
            raise ValueError(f"Action {action} not found in skill {skill_name}")
        
        return await handler(**kwargs)
    
    def load_from_dir(self, dir_path: str):
        """从目录加载技能"""
        for skill_file in Path(dir_path).glob("*/skill.yaml"):
            skill = self.loader.load(skill_file)
            self.register(skill)
```

### 5. DGM - 自我改进 (自研实现)

```python
# src/dgm/engine.py

from typing import Dict, Any, List
import subprocess

class DGMEngine:
    """DGM 自我改进引擎"""
    
    def __init__(self, config: Dict):
        self.model = config["model"]
        self.benchmark = config.get("benchmark", "custom")
        self.enabled = config.get("enabled", True)
    
    async def improve(self, target_code: str, goal: str) -> Dict:
        """改进代码"""
        if not self.enabled:
            return {"status": "disabled"}
        
        # 1. 分析当前代码
        analysis = await self.analyze(target_code)
        
        # 2. 生成改进方案
        improvement = await self.generate_improvement(analysis, goal)
        
        # 3. 应用改进
        improved_code = await self.apply_improvement(target_code, improvement)
        
        # 4. 验证改进
        score_before = await self.benchmark.run(target_code)
        score_after = await self.benchmark.run(improved_code)
        
        return {
            "original_code": target_code,
            "improved_code": improved_code,
            "score_before": score_before,
            "score_after": score_after,
            "improvement": improvement
        }
```

---

## 🚀 快速启动

```bash
# 1. 克隆
git clone https://github.com/your-repo/xuanling.git
cd xuanling

# 2. 安装
pip install -r requirements.txt

# 3. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml

# 4. 运行
python -m src.main

# 5. 测试
curl http://localhost:8000/health
```

---

## 📊 对比 OpenClaw

| 模块 | OpenClaw | 玄灵AI (自研) |
|------|----------|---------------|
| 架构 | Node.js | Python |
| 模型 | 可替换 | 可替换 |
| Gateway | Go/Node | Python FastAPI |
| Skills | Node.js | Python |
| 记忆 | 简化版 | 向量 + SQLite |
| DGM | 独立模块 | 内置引擎 |
| 插件 | ACP 协议 | 自研 |

---

这个架构清晰吗？需要我开始写代码实现吗？🚀
