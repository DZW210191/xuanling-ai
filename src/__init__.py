"""
玄灵AI - 入口文件
"""
import asyncio
import signal
from pathlib import Path
from .gateway import Gateway
from .core import Agent
from .memory import MemoryManager
from .skills import SkillRegistry
from .model import ModelRouter
from .plugins import PluginManager
from .storage import Database
import uvicorn


class XuanlingApp:
    """玄灵AI 应用主类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.db = None
        self.gateway = None
        self.agent = None
        self.memory = None
        self.skills = None
        self.model = None
        self.plugins = None
    
    def _load_config(self, path: str) -> dict:
        """加载配置"""
        import yaml
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except:
            return self._default_config()
    
    def _default_config(self) -> dict:
        """默认配置"""
        return {
            "server": {"host": "0.0.0.0", "port": 8000},
            "model": {
                "provider": "minimax",
                "api_key": "",
                "base_url": "https://api.minimax.chat/v1",
                "model": "MiniMax-M2.5"
            },
            "memory": {
                "short_term_limit": 20,
                "vector_dim": 1536
            },
            "plugins": ["feishu"]
        }
    
    async def initialize(self):
        """初始化"""
        print("🚀 初始化玄灵AI...")
        
        # 1. 初始化数据库
        print("📦 初始化数据库...")
        self.db = Database(self.config.get("database", {}))
        await self.db.init()
        
        # 2. 初始化模型
        print("🤖 初始化模型...")
        self.model = ModelRouter(self.config.get("model", {}))
        
        # 3. 初始化记忆
        print("🧠 初始化记忆系统...")
        self.memory = MemoryManager(self.config.get("memory", {}))
        
        # 4. 初始化技能
        print("🛠️ 加载技能...")
        self.skills = SkillRegistry()
        await self.skills.load_from_dir("skills")
        
        # 5. 初始化 Agent
        print("✨ 初始化 Agent...")
        self.agent = Agent(
            model=self.model,
            memory=self.memory,
            skills=self.skills,
            config=self.config.get("agent", {})
        )
        
        # 6. 初始化插件
        print("🔌 加载插件...")
        self.plugins = PluginManager(self.config.get("plugins", []))
        
        # 7. 初始化网关
        print("🌐 启动网关...")
        self.gateway = Gateway(
            agent=self.agent,
            plugins=self.plugins,
            config=self.config.get("gateway", {})
        )
        
        print("✅ 玄灵AI 启动完成!")
    
    async def run(self):
        """运行"""
        await self.initialize()
        
        # 启动服务器
        config = self.config.get("server", {})
        uvicorn.run(
            "xuanling.main:app",
            host=config.get("host", "0.0.0.0"),
            port=config.get("port", 8000),
            reload=False
        )


app = None

def create_app() -> XuanlingApp:
    """创建应用"""
    global app
    app = XuanlingApp()
    return app


# FastAPI 应用
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="玄灵AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    global app
    app = XuanlingApp()
    await app.initialize()

@app.get("/")
async def root():
    return {"name": "玄灵AI", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    asyncio.run(XuanlingApp().run())
