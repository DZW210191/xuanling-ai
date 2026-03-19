"""
玄灵AI - 主入口
"""
import asyncio
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

# 确保路径正确
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gateway import Gateway, Message
from src.core import Agent
from src.memory import MemoryManager
from src.skills import SkillRegistry
from src.model import ModelRouter
from src.plugins import PluginManager
from src.storage import Database


class XuanlingApp:
    """玄灵AI 应用"""
    
    def __init__(self):
        self.config = self._load_config()
        self.db = None
        self.gateway = None
        self.agent = None
        self.memory = None
        self.model = None
        self.plugins = None
    
    def _load_config(self) -> dict:
        """加载配置"""
        import yaml
        import re
        config = {
            "server": {"host": "0.0.0.0", "port": 8000},
            "model": {"provider": "mock", "api_key": ""},
            "memory": {"short_term_limit": 20},
            "database": {"path": "xuanling.db"},
            "plugins": ["feishu"],
            "gateway": {"rate_limit": {"max_requests": 60, "window": 60}}
        }
        
        config_file = Path(__file__).parent.parent / "config.yaml"
        if config_file.exists():
            with open(config_file) as f:
                config.update(yaml.safe_load(f) or {})
        
        # 处理环境变量替换 ${VAR}
        def replace_env_vars(obj):
            if isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(i) for i in obj]
            elif isinstance(obj, str):
                # 替换 ${VAR} 格式的环境变量
                pattern = r'\$\{(\w+)\}'
                def replacer(match):
                    var_name = match.group(1)
                    return os.getenv(var_name, match.group(0))
                return re.sub(pattern, replacer, obj)
            return obj
        
        config = replace_env_vars(config)
        
        # 环境变量覆盖
        if os.getenv("API_KEY"):
            config["model"]["api_key"] = os.getenv("API_KEY")
        if os.getenv("API_BASE_URL"):
            config["model"]["base_url"] = os.getenv("API_BASE_URL")
        
        # 调试输出
        print(f"📋 Model config: {config.get('model', {})}")
        
        return config
    
    async def initialize(self):
        """初始化"""
        print("🚀 初始化玄灵AI...")
        
        # 1. 数据库
        print("📦 初始化数据库...")
        self.db = Database(self.config.get("database", {}))
        await self.db.init()
        
        # 2. 模型
        print("🤖 初始化模型...")
        self.model = ModelRouter(self.config.get("model", {}))
        
        # 3. 记忆
        print("🧠 初始化记忆系统...")
        self.memory = MemoryManager(self.config.get("memory", {}))
        await self.memory.init(self.db)
        
        # 4. 技能
        print("🛠️ 加载技能...")
        self.skills = SkillRegistry()
        
        # 5. Agent
        print("✨ 初始化 Agent...")
        self.agent = Agent(
            model=self.model,
            memory=self.memory,
            skills=self.skills,
            config=self.config.get("agent", {"name": "玄灵AI"})
        )
        
        # 6. 插件
        print("🔌 加载插件...")
        self.plugins = PluginManager(self.config.get("plugins", []))
        await self.plugins.on_start()
        
        # 7. Gateway
        print("🌐 启动网关...")
        self.gateway = Gateway(
            agent=self.agent,
            plugins=self.plugins,
            config=self.config.get("gateway", {})
        )
        
        print("✅ 玄灵AI 启动完成!")
        print(f"📍 服务地址: http://{self.config['server']['host']}:{self.config['server']['port']}")


# FastAPI 应用
app = FastAPI(title="玄灵AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

xuanling_app = None


@app.on_event("startup")
async def startup():
    global xuanling_app
    xuanling_app = XuanlingApp()
    await xuanling_app.initialize()
    
    # 启动任务调度器
    from src.scheduler import scheduler, init_default_tasks
    init_default_tasks()
    scheduler.start()


@app.get("/")
async def root():
    static_index = Path(__file__).parent.parent / "static" / "index.html"
    if static_index.exists():
        return FileResponse(static_index, media_type="text/html")
    return {"name": "玄灵AI", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/chat")
async def chat(message: str, user_id: str = "user"):
    """聊天接口"""
    if xuanling_app:
        response = await xuanling_app.gateway.handle_web(message, user_id)
        return response.to_dict()
    return {"message": "系统未初始化"}


@app.post("/chat/json")
async def chat_json(body: dict):
    """聊天接口 (JSON body)"""
    message = body.get("message", "")
    user_id = body.get("user_id", "user")
    if xuanling_app:
        response = await xuanling_app.gateway.handle_web(message, user_id)
        return response.to_dict()
    return {"message": "系统未初始化"}


@app.get("/memory")
async def get_memory():
    """获取记忆"""
    if xuanling_app:
        memories = await xuanling_app.memory.get_all_memories()
        # 可能是 dict 或对象
        if memories and hasattr(memories[0], 'to_dict'):
            return {"memories": [m.to_dict() for m in memories]}
        return {"memories": memories}
    return {"memories": []}


@app.post("/memory")
async def add_memory(title: str = "", content: str = "", tags: str = ""):
    """添加记忆"""
    if not title:
        return {"status": "error", "message": "title is required"}
    if xuanling_app:
        tag_list = tags.split(",") if tags else []
        memory = await xuanling_app.memory.add_memory(title, content, tag_list)
        if memory:
            return {"status": "ok", "memory": memory.to_dict()}
    return {"status": "error"}


@app.post("/memory/json")
async def add_memory_json(body: dict):
    """添加记忆 (JSON)"""
    title = body.get("title", "")
    content = body.get("content", "")
    tags = body.get("tags", "")
    if not title:
        return {"status": "error", "message": "title is required"}
    if xuanling_app:
        tag_list = tags.split(",") if tags else []
        memory = await xuanling_app.memory.add_memory(title, content, tag_list)
        if memory:
            return {"status": "ok", "memory": memory.to_dict()}
    return {"status": "error"}


@app.get("/projects")
async def get_projects():
    """获取项目"""
    if xuanling_app:
        return {"projects": await xuanling_app.db.get_projects()}
    return {"projects": []}


@app.post("/projects")
async def create_project(name: str = "", description: str = "", icon: str = "📁"):
    """创建项目 - 同时创建数据库记录和磁盘文件夹"""
    if not name:
        return {"status": "error", "message": "name is required"}
    if xuanling_app:
        # 1. 创建数据库记录
        project_id = await xuanling_app.db.create_project(name, description, icon)
        
        # 2. 创建磁盘文件夹
        from src.projects import project_manager
        folder_result = project_manager.create_project(name, description)
        
        return {"status": "ok", "id": project_id, "folder": folder_result}
    return {"status": "error"}


@app.post("/projects/json")
async def create_project_json(body: dict):
    """创建项目 (JSON) - 同时创建数据库记录和磁盘文件夹"""
    name = body.get("name", "")
    description = body.get("description", "")
    icon = body.get("icon", "📁")
    if not name:
        return {"status": "error", "message": "name is required"}
    if xuanling_app:
        # 1. 创建数据库记录
        project_id = await xuanling_app.db.create_project(name, description, icon)
        
        # 2. 创建磁盘文件夹
        from src.projects import project_manager
        folder_result = project_manager.create_project(name, description)
        
        return {"status": "ok", "id": project_id, "folder": folder_result}
    return {"status": "error"}


@app.put("/projects/{project_id}")
async def update_project(project_id: int, body: dict = None):
    """更新项目"""
    if body is None:
        body = {}
    name = body.get("name")
    description = body.get("description")
    status = body.get("status")
    icon = body.get("icon")
    if xuanling_app:
        await xuanling_app.db.update_project(project_id, name, description, status, icon)
        return {"status": "ok"}
    return {"status": "error"}


@app.delete("/projects/{project_id}")
async def delete_project(project_id: int):
    """删除项目"""
    if xuanling_app:
        await xuanling_app.db.delete_project(project_id)
        return {"status": "ok"}
    return {"status": "error"}


@app.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """删除记忆"""
    if xuanling_app:
        await xuanling_app.memory.delete_memory(memory_id)
        return {"status": "ok"}
    return {"status": "error"}


# ============ 模型配置接口 ============
# 内置模型列表
BUILTIN_MODELS = [
    {"id": "minimax", "name": "MiniMax", "default_url": "https://code.coolyeah.net/v1", "default_model": "MiniMax-M2.5"},
    {"id": "openai", "name": "OpenAI", "default_url": "https://api.openai.com/v1", "default_model": "gpt-4"},
    {"id": "anthropic", "name": "Claude", "default_url": "https://api.anthropic.com/v1", "default_model": "claude-3-opus-20240229"},
    {"id": "custom", "name": "自定义", "default_url": "", "default_model": ""},
]


@app.get("/models")
async def list_models():
    """获取可用模型列表"""
    if xuanling_app:
        current = xuanling_app.config.get("model", {})
        current_provider = current.get("provider", "mock")
        current_url = current.get("base_url", "")
        current_key = current.get("api_key", "")
        current_model = current.get("model", "")
        
        # 合并内置模型和自定义模型
        models = []
        for m in BUILTIN_MODELS:
            is_active = (m["id"] == current_provider)
            models.append({
                **m,
                "is_active": is_active,
                "url": current_url if is_active else m["default_url"],
                "model": current_model if is_active else m["default_model"]
            })
        
        return {
            "models": models,
            "current": {
                "provider": current_provider,
                "url": current_url,
                "model": current_model,
                "has_key": bool(current_key and len(current_key) > 5)
            }
        }
    return {"models": BUILTIN_MODELS}


@app.post("/models")
async def add_model(body: dict = None):
    """添加自定义模型"""
    if body is None:
        body = {}
    name = body.get("name")
    url = body.get("url")
    model = body.get("model")
    
    # 保存到配置文件
    config_file = Path(__file__).parent.parent / "config.yaml"
    import yaml
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    if "custom_models" not in config:
        config["custom_models"] = []
    
    config["custom_models"].append({
        "name": name,
        "url": url,
        "model": model
    })
    
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    return {"status": "ok", "message": f"已添加模型: {name}"}


@app.post("/models/{provider}/activate")
async def activate_model(provider: str, body: dict = None):
    """激活模型"""
    if body is None:
        body = {}
    api_key = body.get("api_key", "")
    api_url = body.get("api_url", "")
    model = body.get("model", "")
    
    # 保存到配置文件 - 修复路径
    config_file = Path(__file__).parent.parent / "config.yaml"
    print(f"📁 配置文件路径: {config_file}")
    import yaml
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # 更新配置
    config["model"]["provider"] = provider
    
    # 获取默认URL
    for m in BUILTIN_MODELS:
        if m["id"] == provider:
            if not api_url:
                api_url = m["default_url"]
            if not model:
                model = m["default_model"]
            break
    
    if api_key:
        config["model"]["api_key"] = api_key
    if api_url:
        config["model"]["base_url"] = api_url
    if model:
        config["model"]["model"] = model
    
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    # 重新加载配置并重建组件
    if xuanling_app:
        xuanling_app.config = xuanling_app._load_config()
        xuanling_app.model = ModelRouter(xuanling_app.config.get("model", {}))
        xuanling_app.agent = Agent(
            model=xuanling_app.model,
            memory=xuanling_app.memory,
            skills=xuanling_app.skills,
            config=xuanling_app.config.get("agent", {"name": "玄灵AI"})
        )
        xuanling_app.gateway = Gateway(
            agent=xuanling_app.agent,
            plugins=xuanling_app.plugins,
            config=xuanling_app.config.get("gateway", {})
        )
    
    return {"status": "ok", "message": f"已激活模型: {provider}", "config": config["model"]}


# ============ API配置接口 ============
@app.get("/config")
async def get_config():
    """获取API配置"""
    if xuanling_app:
        model_cfg = xuanling_app.config.get("model", {})
        return {
            "api_url": model_cfg.get("base_url", ""),
            "api_key": model_cfg.get("api_key", "")[:10] + "..." if model_cfg.get("api_key") else "",
            "model": model_cfg.get("model", ""),
            "provider": model_cfg.get("provider", "")
        }
    return {}


@app.post("/config")
async def update_config(body: dict = None):
    """更新API配置（内存）"""
    if body is None:
        body = {}
    api_url = body.get("api_url")
    api_key = body.get("api_key")
    model = body.get("model")
    
    if xuanling_app:
        # 更新内存配置
        if api_url:
            xuanling_app.config["model"]["base_url"] = api_url
        if api_key:
            xuanling_app.config["model"]["api_key"] = api_key
        if model:
            xuanling_app.config["model"]["model"] = model
        
        # 重新创建模型实例
        xuanling_app.model = ModelRouter(xuanling_app.config.get("model", {}))
        
        # 重建Agent
        xuanling_app.agent = Agent(
            model=xuanling_app.model,
            memory=xuanling_app.memory,
            skills=xuanling_app.skills,
            config=xuanling_app.config.get("agent", {"name": "玄灵AI"})
        )
        
        # 重建Gateway
        xuanling_app.gateway = Gateway(
            agent=xuanling_app.agent,
            plugins=xuanling_app.plugins,
            config=xuanling_app.config.get("gateway", {})
        )
        
        return {"status": "ok", "message": "配置已更新（仅内存）"}
    return {"status": "error"}


# ============ 技能接口 ============
@app.get("/skills")
async def list_skills():
    """获取技能列表"""
    if xuanling_app:
        skills = xuanling_app.skills.get_skills()
        # 如果没有加载到技能，返回默认列表
        if not skills:
            return {
                "skills": [
                    {"name": "💬 对话技能", "description": "智能对话和问答能力", "version": "1.0.0", "tools": ["chat", "qa"]},
                    {"name": "🧠 记忆技能", "description": "长期和短期记忆管理", "version": "1.0.0", "tools": ["memory"]},
                    {"name": "🛠️ 工具技能", "description": "调用外部工具执行各种任务", "version": "1.0.0", "tools": ["tools"]},
                    {"name": "🔌 插件技能", "description": "飞书、Telegram集成", "version": "1.0.0", "tools": ["feishu", "telegram"]},
                    {"name": "📝 写作技能", "description": "文章、文案创作", "version": "1.0.0", "tools": ["writing"]},
                    {"name": "💻 编程技能", "description": "代码编写和调试", "version": "1.0.0", "tools": ["coding"]}
                ]
            }
        return {"skills": skills}
    return {"skills": []}


@app.get("/skills/{skill_name}")
async def get_skill(skill_name: str):
    """获取单个技能详情"""
    if xuanling_app:
        skill = xuanling_app.skills.skills.get(skill_name)
        if skill:
            return skill.to_dict()
    return {"error": "Skill not found"}


# ============ 后台任务接口 ============
@app.get("/bg-tasks")
async def list_bg_tasks():
    """列出所有后台任务"""
    from src.tasks import task_manager
    return {"tasks": task_manager.list_tasks()}


@app.get("/bg-tasks/{task_id}")
async def get_bg_task(task_id: str):
    """获取任务状态"""
    from src.tasks import task_manager
    task = task_manager.get_task(task_id)
    if task:
        return task.to_dict()
    return {"error": "Task not found"}


# ============ 任务调度接口 ============
@app.get("/tasks")
async def list_tasks():
    """列出所有任务"""
    from src.scheduler import scheduler
    return {"tasks": scheduler.list_tasks()}


@app.post("/tasks")
async def add_task(body: dict = None):
    """添加任务"""
    if body is None:
        body = {}
    name = body.get("name", "")
    interval = body.get("interval", 60)  # 默认60秒
    
    if not name:
        return {"status": "error", "message": "name is required"}
    
    from src.scheduler import scheduler
    
    # 创建一个简单的任务
    async def custom_task():
        print(f"🔄 执行任务: {name}")
    
    scheduler.add_task(name, custom_task, interval=interval)
    return {"status": "ok", "task": name, "interval": interval}


@app.post("/tasks/{task_name}/run")
async def run_task(task_name: str):
    """手动执行任务"""
    from src.scheduler import scheduler
    scheduler.run_task(task_name)
    return {"status": "ok", "task": task_name}


@app.delete("/tasks/{task_name}")
async def remove_task(task_name: str):
    """移除任务"""
    from src.scheduler import scheduler
    scheduler.remove_task(task_name)
    return {"status": "ok"}


# ============ 项目文件管理接口 ============
@app.get("/project-manager/projects")
async def list_all_projects():
    """列出所有项目"""
    from src.projects import project_manager
    return {"projects": project_manager.list_projects()}


@app.post("/project-manager/projects")
async def create_project(body: dict = None):
    """创建项目"""
    if body is None:
        body = {}
    name = body.get("name", "")
    description = body.get("description", "")
    
    if not name:
        return {"status": "error", "message": "项目名称不能为空"}
    
    from src.projects import project_manager
    result = project_manager.create_project(name, description)
    return result


@app.get("/project-manager/projects/{project_name}")
async def get_project_detail(project_name: str):
    """获取项目详情"""
    from src.projects import project_manager
    return project_manager.get_project(project_name)


@app.delete("/project-manager/projects/{project_name}")
async def delete_project_file(project_name: str):
    """删除项目"""
    from src.projects import project_manager
    return project_manager.delete_project(project_name)


@app.post("/project-manager/projects/{project_name}/memory")
async def add_project_memory(project_name: str, body: dict = None):
    """添加项目记忆"""
    if body is None:
        body = {}
    title = body.get("title", "")
    content = body.get("content", "")
    tags = body.get("tags", [])
    
    from src.projects import project_manager
    return project_manager.add_memory(project_name, title, content, tags)


@app.post("/project-manager/projects/{project_name}/docs")
async def add_project_doc(project_name: str, body: dict = None):
    """添加项目文档"""
    if body is None:
        body = {}
    title = body.get("title", "")
    content = body.get("content", "")
    
    from src.projects import project_manager
    return project_manager.add_doc(project_name, title, content)


@app.get("/project-manager/projects/{project_name}/files/{file_path:path}")
async def read_project_file(project_name: str, file_path: str):
    """读取项目文件"""
    from src.projects import project_manager
    content = project_manager.read_file(project_name, file_path)
    return {"content": content}


@app.put("/project-manager/projects/{project_name}/files/{file_path:path}")
async def write_project_file(project_name: str, file_path: str, body: dict = None):
    """写入项目文件"""
    if body is None:
        body = {}
    content = body.get("content", "")
    from src.projects import project_manager
    result = project_manager.write_file(project_name, file_path, content)
    return result


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
