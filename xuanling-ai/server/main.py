"""
玄灵AI 后端 - FastAPI 主入口 (增强版)
修复: 数据持久化、安全性、异常处理、真实AI对接
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

# ============== 日志配置 ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("玄灵AI")

# ============== 获取静态文件路径 ==============
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
# 应用内数据根目录（存放项目与子代理数据）
APP_DATA_ROOT = BASE_DIR / "appdata"
PROJECTS_DIR = APP_DATA_ROOT / "projects"
AGENTS_DIR = APP_DATA_ROOT / "agents"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_DIR.mkdir(parents=True, exist_ok=True)

# ============== 配置 ==============
# 从环境变量读取，生产环境请配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
SETTINGS_FILE = "settings.json"

# 加载或初始化设置
def load_settings():
    """从文件加载设置"""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"model": "MiniMax-M2.5", "apiUrl": "https://api.minimax.chat/v1", "apiKey": ""}

def save_settings_to_file(settings: dict):
    """保存设置到文件（不包含 API Key）"""
    to_save = {"model": settings.get("model"), "apiUrl": settings.get("apiUrl")}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)
    logger.info(f"设置已保存到文件: model={to_save.get('model')}, apiUrl={to_save.get('apiUrl')}, apiKey=不落盘")

# 全局设置
app_settings = load_settings()

# ============== 数据库模拟 (生产环境请使用真实数据库) ==============
# 使用内存存储 + 简单持久化到 JSON 文件
import json
import threading

DATA_FILE = "data.json"

def load_data():
    """从文件加载数据"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"projects": [], "memories": [], "next_ids": {"project": 1, "memory": 1}}

def save_data(data):
    """保存数据到文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 线程安全的全局数据存储
data_lock = threading.Lock()
_data = load_data()

def get_projects():
    with data_lock:
        return _data.get("projects", [])

def get_memories():
    with data_lock:
        return _data.get("memories", [])

def save_project(project_data):
    with data_lock:
        _data["projects"].append(project_data)
        save_data(_data)
        return project_data

def save_memory(memory_data):
    with data_lock:
        _data["memories"].append(memory_data)
        save_data(_data)
        return memory_data

# 初始化默认数据
if not _data["projects"]:
    _data["projects"] = [
        {"id": 1, "name": "AI 智能代理框架", "description": "基于 OpenClaw 构建", "icon": "🤖", "status": "进行中", "progress": 65, "tasks": 12, "memory": 5},
        {"id": 2, "name": "Web 控制台", "description": "玄灵AI 管理界面", "icon": "🌐", "status": "进行中", "progress": 80, "tasks": 8, "memory": 3},
    ]
    _data["next_ids"]["project"] = 3

# 确保首次启动时默认项目也持久化到 data.json
try:
    save_data(_data)
except Exception as _e:
    logger.error(f"初始化持久化失败: {_e}")

if not _data["memories"]:
    _data["memories"] = [
        {"id": 1, "title": "主人称呼偏好", "content": "喜欢被称呼为老板", "tags": ["个人"], "importance": 5, "project_id": None},
        {"id": 2, "title": "最喜欢的颜色", "content": "蓝色", "tags": ["偏好"], "importance": 3, "project_id": None},
        {"id": 3, "title": "AI 项目", "content": "正在做 AI 项目", "tags": ["重要"], "importance": 5, "project_id": None},
    ]
    _data["next_ids"]["memory"] = 4
    save_data(_data)

# ============== FastAPI 应用 ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 玄灵AI 后端启动")
    yield
    logger.info("🛑 玄灵AI 后端关闭")

app = FastAPI(title="玄灵AI API", version="1.1.0", lifespan=lifespan)

# ============== CORS 中间件 (安全配置) ==============
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ============== 全局异常处理 ==============

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误，请稍后重试"}
    )

# ============== 数据模型 ==============

class ChatRequest(BaseModel):
    message: str
    project_id: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    agent: str = "玄灵AI"

class Project(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = ""
    icon: Optional[str] = "📁"
    status: Optional[str] = "进行中"
    progress: Optional[int] = 0
    tasks: Optional[int] = 0
    memory: Optional[int] = 0

class Memory(BaseModel):
    id: Optional[int] = None
    title: str
    content: str
    tags: List[str] = []
    project_id: Optional[int] = None
    importance: int = 1

# 子代理与文件写入请求模型
class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class AgentUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None

class AgentMemoryCreate(BaseModel):
    title: str
    content: Optional[str] = ""

class FileSave(BaseModel):
    content: str = ""

# ============== 真实 AI 对接 (MiniMax) ==============

async def call_minimax_ai(user_message: str) -> str:
    """调用 MiniMax AI API - 使用保存的设置"""
    # 优先使用保存的设置，否则回退到环境变量
    api_key = app_settings.get("apiKey") or MINIMAX_API_KEY
    api_url = app_settings.get("apiUrl") or MINIMAX_BASE_URL
    model = app_settings.get("model") or "MiniMax-M2.5"
    
    if not api_key or api_key == "test-key":
        logger.warning("未配置有效的 API Key，使用模拟回复")
        return await mock_ai_response(user_message)
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是玄灵AI，一个友好、聪明的AI助手。"},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            # MiniMax API 认证方式
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            # 兼容不同 API 格式
            if "minimax" in api_url:
                endpoint = f"{api_url}/text/chatcompletion_v2"
            else:
                endpoint = f"{api_url}/chat/completions"
            
            async with session.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # 兼容不同返回格式
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        return msg.get("content", msg.get("text", "抱歉，AI 响应为空"))
                    
                    # 检查是否有错误
                    if data.get("base_resp", {}).get("status_msg"):
                        error_msg = data["base_resp"]["status_msg"]
                        logger.error(f"AI API 返回错误: {error_msg}")
                        return f"API 错误: {error_msg}"
                    
                    return "抱歉，AI 响应为空"
                else:
                    error_text = await resp.text()
                    logger.error(f"AI API 错误: {resp.status} - {error_text}")
                    return f"API 错误 ({resp.status}): {error_text[:100]}"
    except ImportError:
        logger.warning("aiohttp 未安装，使用模拟回复")
        return await mock_ai_response(user_message)
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        return await mock_ai_response(user_message)

async def mock_ai_response(message: str) -> str:
    """模拟 AI 回复 (当没有 API Key 时使用)"""
    msg = message.lower()
    
    # 智能关键词匹配
    if "你好" in msg or "hi" in msg or "hello" in msg:
        return "你好！我是玄灵AI，很高兴见到你！有什么我可以帮你的吗？"
    elif "项目" in msg:
        projects = get_projects()
        if projects:
            project_list = "\n".join([f"- {p['icon']} {p['name']}: {p['description']}" for p in projects])
            return f"当前有 {len(projects)} 个项目正在进行中:\n{project_list}"
        return "目前没有项目记录"
    elif "记忆" in msg or "记得" in msg:
        memories = get_memories()
        if memories:
            important = [m for m in memories if m.get("importance", 0) >= 3]
            return f"我记住了 {len(memories)} 条信息，其中 {len(important)} 条是重要的"
        return "还没有记忆记录"
    elif "帮助" in msg or "help" in msg:
        return """我可以帮你:
- 📁 管理项目 (查看、创建)
- 🧠 管理记忆 (添加、查询)
- 💬 对话交流
直接告诉我你需要什么吧！"""
    else:
        return f"收到你的消息: {message}\n\n你可以问我关于项目、记忆的问题，或者获取帮助"

# ============== API 路由 ==============

@app.get("/")
def root():
    """返回前端首页"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": "玄灵AI API", 
        "version": "1.1.0",
        "status": "healthy"
    }

@app.get("/console")
def console_page():
    """返回控制台页面"""
    console_file = STATIC_DIR / "console.html"
    if console_file.exists():
        return FileResponse(str(console_file))
    return {"message": "控制台不存在"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    对话接口 (真实 AI 对接)
    """
    logger.info(f"收到消息: {request.message}")
    
    try:
        # 调用 AI
        response = await call_minimax_ai(request.message)
        logger.info(f"AI 回复: {response[:50]}...")
        return ChatResponse(response=response)
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail="对话处理失败")

@app.get("/projects")
def get_projects_list():
    """获取项目列表"""
    return {"projects": get_projects()}

@app.post("/projects")
def create_project(project: Project):
    """创建项目"""
    logger.info(f"创建项目: {project.name}")
    
    if not project.name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    
    with data_lock:
        new_id = _data["next_ids"]["project"]
        _data["next_ids"]["project"] += 1
        
        new_project = {
            "id": new_id,
            "name": project.name,
            "description": project.description or "",
            "icon": project.icon or "📁",
            "status": project.status or "进行中",
            "progress": project.progress or 0,
            "tasks": project.tasks or 0,
            "memory": project.memory or 0,
            "created_at": datetime.now().isoformat()
        }
        _data["projects"].append(new_project)
        save_data(_data)
    
    # 在工作区自动创建项目文件夹与 README
    proj_dir = PROJECTS_DIR / project.name
    try:
        proj_dir.mkdir(parents=True, exist_ok=True)
        readme = proj_dir / "README.md"
        if not readme.exists():
            readme.write_text(f"# {project.name}\n\n{project.description or ''}\n\n创建时间: {datetime.now().isoformat()}\n", encoding="utf-8")
    except Exception as e:
        logger.error(f"初始化项目目录失败: {e}")
    
    return new_project

@app.put("/projects/{project_id}")
def update_project(project_id: int, project: Project):
    """更新项目（局部更新）"""
    logger.info(f"更新项目: {project_id}")
    
    with data_lock:
        for i, p in enumerate(_data["projects"]):
            if p["id"] == project_id:
                updated = p.copy()
                if project.name is not None:
                    updated["name"] = project.name
                if project.description is not None:
                    updated["description"] = project.description
                if project.icon is not None:
                    updated["icon"] = project.icon
                if project.status is not None:
                    updated["status"] = project.status
                if project.progress is not None:
                    updated["progress"] = project.progress
                if project.tasks is not None:
                    updated["tasks"] = project.tasks
                if project.memory is not None:
                    updated["memory"] = project.memory
                updated["updated_at"] = datetime.now().isoformat()
                _data["projects"][i] = updated
                save_data(_data)
                return updated
    
    raise HTTPException(status_code=404, detail="项目不存在")

@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    """删除项目"""
    logger.info(f"删除项目: {project_id}")
    
    with data_lock:
        for i, p in enumerate(_data["projects"]):
            if p["id"] == project_id:
                deleted = _data["projects"].pop(i)
                save_data(_data)
                return {"message": "删除成功", "project": deleted}
    
    raise HTTPException(status_code=404, detail="项目不存在")

@app.get("/api/memory")
def get_memory_list(project_id: Optional[int] = None):
    """获取记忆列表"""
    memories = get_memories()
    if project_id:
        return [m for m in memories if m.get("project_id") == project_id]
    return memories

# 兼容 /memory 路由（前端旧逻辑）
@app.get("/memory")
def get_memory_list_compat(project_id: Optional[int] = None):
    memories = get_memories()
    if project_id:
        memories = [m for m in memories if m.get("project_id") == project_id]
    return {"memories": memories}

@app.post("/memory")
def create_memory_compat(memory: Memory):
    created = create_memory(memory)  # 复用主实现
    return {"memory": created, "status": "ok"}

@app.delete("/memory/{memory_id}")
def delete_memory_compat(memory_id: int):
    return delete_memory(memory_id)

@app.post("/api/memory")
def create_memory(memory: Memory):
    """创建记忆"""
    logger.info(f"创建记忆: {memory.title}")
    
    if not memory.title:
        raise HTTPException(status_code=400, detail="记忆标题不能为空")
    
    with data_lock:
        new_id = _data["next_ids"]["memory"]
        _data["next_ids"]["memory"] += 1
        
        new_memory = {
            "id": new_id,
            "title": memory.title,
            "content": memory.content,
            "tags": memory.tags,
            "project_id": memory.project_id,
            "importance": memory.importance,
            "created_at": datetime.now().isoformat()
        }
        _data["memories"].append(new_memory)
        save_data(_data)
    
    return new_memory

@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int):
    """删除记忆"""
    logger.info(f"删除记忆: {memory_id}")
    
    with data_lock:
        for i, m in enumerate(_data["memories"]):
            if m["id"] == memory_id:
                deleted = _data["memories"].pop(i)
                save_data(_data)
                return {"message": "删除成功", "memory": deleted}
    
    raise HTTPException(status_code=404, detail="记忆不存在")

@app.get("/api/tasks")
def get_tasks():
    """获取定时任务"""
    return [
        {"id": 1, "name": "每日早间简报", "schedule": "0 8 * * *", "status": "running"},
        {"id": 2, "name": "健康检查", "schedule": "0 * * * *", "status": "running"},
        {"id": 3, "name": "自动备份", "schedule": "0 2 * * *", "status": "paused"},
        {"id": 4, "name": "周报汇总", "schedule": "0 9 * * 1", "status": "running"},
    ]

@app.get("/api/agents")
def get_agents():
    """获取子代理"""
    return [
        {"id": 1, "name": "代码审查代理", "status": "running", "tasks": 12, "success_rate": 0.92},
        {"id": 2, "name": "文档助手", "status": "running", "tasks": 8, "success_rate": 1.0},
        {"id": 3, "name": "网页抓取代理", "status": "idle", "tasks": 5, "success_rate": 1.0},
    ]

@app.get("/api/skills")
def get_skills():
    """获取 Skills"""
    return [
        {"name": "feishu-doc", "installed": True},
        {"name": "DGM Skill", "installed": True},
        {"name": "tencent-cos", "installed": False},
    ]

# ============== 设置 API ==============

class SettingsRequest(BaseModel):
    model: str
    apiUrl: str
    apiKey: Optional[str] = None

@app.get("/api/settings")
def get_settings():
    """获取设置"""
    return app_settings

@app.post("/api/settings")
def save_settings(settings: SettingsRequest):
    """保存设置"""
    logger.info(f"保存设置: model={settings.model}, apiUrl={settings.apiUrl}")
    
    global app_settings
    # 保存到全局变量（包括 apiKey，用于本次会话）
    app_settings = {
        "model": settings.model,
        "apiUrl": settings.apiUrl,
        "apiKey": settings.apiKey or ""  # 仅存内存，不写入文件
    }
    # 保存非敏感配置到文件
    save_settings_to_file(app_settings)
    
    return {"message": "设置已保存", "settings": app_settings}

@app.get("/api/monitor")
def get_monitor():
    """获取系统监控"""
    return {
        "cpu": 35,
        "memory": 48,
        "tasks_active": 3,
        "api_usage": 85,
    }

@app.get("/api/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "data_file_exists": os.path.exists(DATA_FILE)
    }

# ============== 兼容前端路由 ==============

# 兼容 /health
@app.get("/health")
def health_compat():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# 后端日志尾部输出（用于“本地运行状态”监控）
@app.get("/api/logs")
def tail_logs(lines: int = 80):
    log_path = Path('/tmp/xuanling.log')
    if not log_path.exists():
        return HTMLResponse("无日志文件")
    try:
        content = log_path.read_text(encoding='utf-8')
        # 取末尾 N 行
        parts = content.splitlines()[-lines:]
        return HTMLResponse("\n".join(parts))
    except Exception as e:
        return HTMLResponse(f"读取日志失败: {e}")

# 兼容 /config GET/POST
@app.get("/config")
def get_config():
    return {
        "api_url": app_settings.get("apiUrl", ""),
        "model": app_settings.get("model", "MiniMax-M2.5"),
        "provider": "minimax"
    }

@app.post("/config")
async def save_config(request: Request):
    # 将 /config 保存兼容到 /api/settings
    try:
        body = await request.json()
    except Exception:
        body = {}
    global app_settings
    model = body.get('model') or app_settings.get('model')
    api_url = body.get('api_url') or body.get('apiUrl') or app_settings.get('apiUrl')
    api_key = body.get('api_key') or body.get('apiKey')
    # 更新内存配置并落盘非敏感
    app_settings = {"model": model, "apiUrl": api_url, "apiKey": api_key or app_settings.get('apiKey', '')}
    save_settings_to_file(app_settings)
    return {"status": "ok", "message": "配置已保存"}

# 兼容 /models GET
@app.get("/models")
def get_models():
    return {
        "models": [
            {"id": "minimax", "name": "MiniMax M2.5", "is_active": True},
            {"id": "openai", "name": "GPT-4", "is_active": False}
        ],
        "current": {
            "provider": "minimax",
            "model": app_settings.get("model", "MiniMax-M2.5"),
            "url": app_settings.get("apiUrl", "")
        }
    }

# 兼容 /models/{id}/activate POST
@app.post("/models/{provider_id}/activate")
def activate_model(provider_id: str, request: Request):
    return {"status": "ok"}

# 兼容 /project-manager/projects
@app.get("/project-manager/projects")
def get_projects_compat():
    return {"projects": get_projects(), "status": "ok"}

# 兼容 /project-manager/projects/{name}
@app.get("/project-manager/projects/{project_name}")
def get_project_detail(project_name: str):
    # 安全列出项目目录下文件（限定到 server/ 静态根的上级工作区）
    # 这里示例使用 workspace 根目录的同名文件夹作为项目根
    project_root = PROJECTS_DIR / project_name
    files = []
    if project_root.exists() and project_root.is_dir():
        for path in project_root.rglob('*'):
            if path.is_file():
                # 只统计合理大小的文本/代码文件
                try:
                    rel = path.relative_to(project_root).as_posix()
                    size = path.stat().st_size
                    # 跳过敏感/隐藏目录和大文件
                    if any(part.startswith('.') for part in path.parts):
                        continue
                    if size > 2 * 1024 * 1024:  # >2MB 不展示
                        continue
                    files.append({"path": rel, "size": size})
                except Exception:
                    continue
    return {"project": {"name": project_name}, "files": files, "status": "ok"}


# 兼容 /agents
# 子代理内存占位存储
_agents_state = {
    1: {"id": 1, "name": "代码审查代理", "status": "running", "tasks_count": 12, "success_rate": 0.92, "description": "自动审查代码"},
    2: {"id": 2, "name": "文档助手", "status": "running", "tasks_count": 8, "success_rate": 1.0, "description": "生成文档"},
    3: {"id": 3, "name": "网页抓取代理", "status": "idle", "tasks_count": 5, "success_rate": 1.0, "description": "抓取网页"}
}
_next_agent_id = 4
_agent_memories = {1: {}, 2: {}, 3: {}}
_agent_tasks = {1: [], 2: [], 3: []}

# 子代理持久化：在 /workspace/agents/{id}-{name}/ 目录下维护 memory.json 与 tasks.json

def _agent_dir(agent_id: int, name: str) -> Path:
    safe_name = ''.join(c for c in name if c.isalnum() or c in ('-','_'))[:50] or f"agent{agent_id}"
    d = AGENTS_DIR / f"{agent_id}-{safe_name}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.load(path.open('r', encoding='utf-8'))
    except Exception:
        pass
    return default

def _save_json(path: Path, data):
    try:
        json.dump(data, path.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入 {path} 失败: {e}")

@app.get("/agents")
def list_agents():
    return {"agents": list(_agents_state.values())}

@app.post("/agents")
def create_agent(payload: AgentCreate):
    global _next_agent_id
    if not payload.name:
        raise HTTPException(status_code=400, detail="子代理名称不能为空")
    agent = {
        "id": _next_agent_id,
        "name": payload.name,
        "description": payload.description or "",
        "status": "idle",
        "tasks_count": 0,
        "success_rate": 1.0
    }
    _agents_state[_next_agent_id] = agent
    _agent_memories[_next_agent_id] = {}
    _agent_tasks[_next_agent_id] = []
    # 初始化记忆与任务持久化文件
    d = _agent_dir(_next_agent_id, payload.name)
    _save_json(d / 'memory.json', {})
    _save_json(d / 'tasks.json', [])
    _next_agent_id += 1
    return {"status": "ok", "agent": agent}

@app.put("/agents/{agent_id}")
def update_agent(agent_id: int, payload: AgentUpdate):
    agent = _agents_state.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="子代理不存在")
    if payload.description is not None:
        agent["description"] = payload.description
    if payload.status is not None:
        agent["status"] = payload.status
    # 追加一条任务历史（状态变更视为任务）
    d = _agent_dir(agent_id, agent["name"])
    tasks = _load_json(d / 'tasks.json', [])
    tasks.append({"ts": datetime.now().isoformat(), "task": "status_update", "status": agent["status"]})
    _save_json(d / 'tasks.json', tasks)
    return {"status": "ok", "agent": agent}

@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: int):
    if agent_id not in _agents_state:
        raise HTTPException(status_code=404, detail="子代理不存在")
    del _agents_state[agent_id]
    _agent_memories.pop(agent_id, None)
    _agent_tasks.pop(agent_id, None)
    return {"status": "ok"}

@app.get("/agents/{agent_id}/memory")
def get_agent_memory(agent_id: int):
    mems = _agent_memories.get(agent_id)
    agent = _agents_state.get(agent_id)
    if mems is None or not agent:
        raise HTTPException(status_code=404, detail="子代理不存在")
    # 合并内存态与持久化文件
    d = _agent_dir(agent_id, agent["name"])
    file_mems = _load_json(d / 'memory.json', {})
    merged = {**file_mems, **mems}
    return {"memories": merged}

@app.post("/agents/{agent_id}/memory")
def add_agent_memory(agent_id: int, payload: AgentMemoryCreate):
    if not payload.title:
        raise HTTPException(status_code=400, detail="记忆标题不能为空")
    agent = _agents_state.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="子代理不存在")
    # 写入内存并持久化
    mems = _agent_memories.setdefault(agent_id, {})
    mem_id = (max(mems.keys()) + 1) if mems else 1
    rec = {"id": mem_id, "title": payload.title, "content": payload.content or ""}
    mems[mem_id] = rec
    d = _agent_dir(agent_id, agent["name"])
    file_mems = _load_json(d / 'memory.json', {})
    file_mems[str(mem_id)] = rec
    _save_json(d / 'memory.json', file_mems)
    return {"status": "ok", "memory": rec}

@app.get("/agents/{agent_id}/tasks")
def get_agent_tasks(agent_id: int):
    agent = _agents_state.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="子代理不存在")
    d = _agent_dir(agent_id, agent["name"])
    tasks = _load_json(d / 'tasks.json', [])
    return {"tasks": tasks}

# 兼容 /chat/json
@app.post("/chat/json")
async def chat_json(request: ChatRequest):
    logger.info(f"收到消息: {request.message}")
    response = await call_minimax_ai(request.message)
    return {"message": response, "status": "ok"}

# 兼容 /skills
@app.get("/skills")
def get_skills_compat():
    return {
        "skills": [
            {"name": "feishu-doc", "description": "飞书文档操作", "tools": ["read", "write"]},
            {"name": "DGM", "description": "自我改进AI", "tools": ["improve"]},
            {"name": "github", "description": "GitHub操作", "tools": ["issue", "pr"]}
        ]
    }

# 兼容 /bg-tasks
@app.get("/bg-tasks")
def get_bg_tasks():
    return {"tasks": []}

# 兼容 /project-manager/projects/{name}/files/{path}
def _safe_project_paths(project_name: str, file_path: str) -> Path:
    project_root = (PROJECTS_DIR / project_name).resolve()
    target = (project_root / file_path).resolve()
    if not str(target).startswith(str(project_root)):
        raise HTTPException(status_code=400, detail="非法路径")
    return target

@app.get("/project-manager/projects/{project_name}/files/{file_path:path}")
def get_project_file(project_name: str, file_path: str):
    target = _safe_project_paths(project_name, file_path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    # 限制读取 1MB 以内的文本文件
    if target.stat().st_size > 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件过大，无法预览")
    try:
        # 以 utf-8 读取，失败则返回提示
        content = target.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=415, detail="非文本文件，无法预览")
    return {"content": content, "status": "ok"}

@app.put("/project-manager/projects/{project_name}/files/{file_path:path}")
def update_project_file(project_name: str, file_path: str, payload: FileSave):
    target = _safe_project_paths(project_name, file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(payload.content or "", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {e}")
    return {"status": "ok", "message": "文件已保存"}

@app.delete("/project-manager/projects/{project_name}")
def delete_project_file(project_name: str):
    return {"status": "ok"}

# ============== 启动 ==============

# 挂载静态文件目录
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"静态文件目录: {STATIC_DIR}")

# ============== 重启 API ==============

@app.post("/api/restart")
def restart_server():
    """重启后端服务"""
    import subprocess
    import sys
    
    def restart_background():
        import time
        time.sleep(2)  # 等待当前请求完成
        # 重新启动服务
        subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "main:app", "--host", "0.0.0.0", "--port", "8000"
        ], cwd=str(BASE_DIR), stdout=open("/tmp/xuanling.log", "a"), stderr=subprocess.STDOUT)
    
    import threading
    thread = threading.Thread(target=restart_background)
    thread.start()
    
    return {"message": "服务正在重启...", "status": "ok"}

if __name__ == "__main__":
    logger.info("启动玄灵AI后端服务...")
    logger.info(f"静态文件目录: {STATIC_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8000)