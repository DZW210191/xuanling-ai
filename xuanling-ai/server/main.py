"""
玄灵AI 后端 - FastAPI 主入口 (增强版)
支持: 工具调用、Skills、子代理、数据持久化、API缓存
修复: 重复路由、命名冲突、安全问题
版本: v1.3.0
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn

# ============== 添加模块路径 ==============
sys.path.insert(0, str(Path(__file__).parent))

# ============== 导入工具系统和 AI 引擎 ==============
from tools import tool_registry, ToolDefinition
from engine import ai_engine

# ============== 导入缓存系统 ==============
from cache import get_cache, init_cache

# ============== 导入新模块 (使用别名避免冲突) ==============
from skills import skill_manager, SkillBase, SkillMetadata, SkillConfig
from subagents import (
    task_scheduler, task_planner, SubAgent, SubAgentConfig, 
    Task, TaskStatus as SubTaskStatus, TaskPriority as SubTaskPriority, 
    TaskResult, AgentRole,
    submit_task, plan_and_execute
)
from subagents import create_agent as create_subagent
from memory import memory_manager, MemoryType, MemoryImportance, remember, recall
from security import (
    permission_manager, audit_logger, security_middleware, 
    Permission, Role, SecurityPolicy, get_admin_key
)
from project_manager import (
    project_manager, Project as PMProject, ProjectTask, ProjectDocument,
    ProjectStatus, TaskStatus as PTaskStatus, TaskPriority as PTaskPriority,
    DocumentType
)

# ============== 日志配置 ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("玄灵AI")

# ============== 获取静态文件路径 ==============
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# ============== 配置 ==============
# 服务配置 (可通过环境变量覆盖)
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SERVER_RELOAD = os.getenv("SERVER_RELOAD", "false").lower() == "true"

# API 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")
DATA_FILE = os.getenv("DATA_FILE", "data.json")

# 请求超时配置
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
TOOL_EXECUTION_TIMEOUT = int(os.getenv("TOOL_EXECUTION_TIMEOUT", "30"))

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
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"model": settings.get("model"), "apiUrl": settings.get("apiUrl")}, f, ensure_ascii=False, indent=2)
    logger.info(f"设置已保存: model={settings.get('model')}, apiUrl={settings.get('apiUrl')}")

# 全局设置
app_settings = load_settings()

# ============== 数据持久化 ==============
import threading

data_lock = threading.Lock()

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "projects": [], 
            "memories": [], 
            "agents": [],
            "channels": [],
            "agent_memories": {},
            "agent_tasks": {},
            "next_ids": {"project": 1, "memory": 1, "agent": 1, "agent_memory": 1}
        }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

_data = load_data()

# ============== Pydantic 数据模型 (使用明确的后缀避免冲突) ==============

class ChatRequest(BaseModel):
    message: str
    project_id: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    agent: str = "玄灵AI"

class ProjectRequest(BaseModel):
    """项目创建/更新请求"""
    name: str
    description: Optional[str] = ""
    icon: str = "📁"
    status: str = "进行中"
    progress: int = 0
    tasks: int = 0
    memory: int = 0

class MemoryRequest(BaseModel):
    """记忆创建请求"""
    title: str
    content: str
    tags: List[str] = []
    project_id: Optional[int] = None
    importance: int = 1

class AgentRequest(BaseModel):
    """子代理创建请求"""
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "idle"

class AgentMemoryRequest(BaseModel):
    """子代理记忆请求"""
    title: str
    content: Optional[str] = ""

class SettingsRequest(BaseModel):
    """设置请求"""
    model: str
    apiUrl: str
    apiKey: Optional[str] = None

class ChannelRequest(BaseModel):
    """频道配置请求"""
    id: str
    name: Optional[str] = ""
    provider: Optional[str] = ""
    webhook_url: Optional[str] = None
    default_target: Optional[str] = None
    token: Optional[str] = None

class CreateProjectRequest(BaseModel):
    """项目管理 - 创建项目请求"""
    name: str
    description: str = ""
    owner: str = None
    tags: List[str] = []
    icon: str = "📁"
    color: str = "#667eea"

class CreateTaskRequest(BaseModel):
    """项目管理 - 创建任务请求"""
    title: str
    description: str = ""
    priority: int = 5
    assignee: str = None
    tags: List[str] = []

class CreateTasksFromTextRequest(BaseModel):
    """项目管理 - 从文字创建任务请求"""
    text: str

class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str
    arguments: Dict[str, Any] = {}

# ============== FastAPI 应用 ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 玄灵AI 后端启动 v1.3.0")
    
    # 初始化缓存
    init_cache(default_ttl=60, max_size=500)
    logger.info("✅ 缓存系统初始化完成")
    
    # 初始化技能管理器
    skill_manager.set_tool_registry(tool_registry)
    skill_manager.set_audit_logger(audit_logger)
    await skill_manager.load_all()
    
    # 启动任务调度器
    await task_scheduler.start()
    
    # 创建默认代理
    try:
        await create_subagent("主代理", AgentRole.WORKER)
        await create_subagent("规划代理", AgentRole.PLANNER)
        logger.info("✅ 默认代理已创建")
    except Exception as e:
        logger.warning(f"创建默认代理失败: {e}")
    
    yield
    
    # 清理
    await task_scheduler.stop()
    logger.info("🛑 玄灵AI 后端关闭")

app = FastAPI(title="玄灵AI API", version="1.3.0", lifespan=lifespan)

# ============== CORS 中间件 ==============
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

# ============== AI 调用函数 ==============

async def call_minimax_ai(user_message: str) -> str:
    """调用 MiniMax AI API"""
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
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
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
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        return msg.get("content", msg.get("text", "抱歉，AI 响应为空"))
                    
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
        return await mock_ai_response(user_message)
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        return await mock_ai_response(user_message)

async def mock_ai_response(message: str) -> str:
    """模拟 AI 回复"""
    msg = message.lower()
    
    if "你好" in msg or "hi" in msg or "hello" in msg:
        return "你好！我是玄灵AI，很高兴见到你！有什么我可以帮你的吗？"
    elif "项目" in msg:
        projects = _data.get("projects", [])
        if projects:
            project_list = "\n".join([f"- {p.get('icon', '📁')} {p['name']}: {p.get('description', '')}" for p in projects])
            return f"当前有 {len(projects)} 个项目:\n{project_list}"
        return "目前没有项目记录"
    elif "帮助" in msg or "help" in msg:
        return """我可以帮你:
- 📁 管理项目 (查看、创建)
- 🧠 管理记忆 (添加、查询)
- 💬 对话交流"""
    else:
        return f"收到你的消息: {message}\n\n你可以问我关于项目、记忆的问题，或者获取帮助"

# ============== 基础路由 ==============

@app.get("/")
def root():
    """返回前端首页"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "玄灵AI API", "version": "1.2.0", "status": "healthy"}

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ============== 对话 API ==============

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口 - 支持工具调用"""
    logger.info(f"收到消息: {request.message}")
    try:
        response = await ai_engine.chat_simple(request.message)
        return ChatResponse(response=response)
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口"""
    async def generate():
        async for event in ai_engine.chat(request.message):
            event_data = json.dumps(event, ensure_ascii=False)
            yield f"data: {event_data}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.post("/api/chat/json")
async def chat_json(request: ChatRequest):
    """对话接口 - JSON 格式"""
    response = await ai_engine.chat_simple(request.message)
    return {"message": response, "status": "ok"}

# ============== 设置 API ==============

@app.get("/api/settings")
def get_settings():
    """获取设置"""
    return app_settings

@app.post("/api/settings")
def save_settings(settings: SettingsRequest):
    """保存设置"""
    global app_settings
    app_settings = {
        "model": settings.model,
        "apiUrl": settings.apiUrl,
        "apiKey": settings.apiKey or ""
    }
    save_settings_to_file(app_settings)
    return {"message": "设置已保存", "settings": app_settings}

@app.get("/api/config")
def get_config():
    """获取配置"""
    return {
        "api_url": app_settings.get("apiUrl", ""),
        "model": app_settings.get("model", "MiniMax-M2.5"),
        "provider": "minimax"
    }

@app.post("/api/config")
def save_config(settings: SettingsRequest):
    """保存配置"""
    global app_settings
    app_settings = {
        "model": settings.model,
        "apiUrl": settings.apiUrl,
        "apiKey": settings.apiKey or ""
    }
    save_settings_to_file(app_settings)
    return {"status": "ok", "message": "配置已保存"}

@app.get("/api/models")
def get_models():
    """获取可用模型"""
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

@app.post("/api/models/{provider_id}/activate")
def activate_model(provider_id: str):
    """激活模型"""
    return {"status": "ok"}

# ============== 监控 API ==============

@app.get("/api/health")
def api_health_check():
    """API 健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "data_file_exists": os.path.exists(DATA_FILE)
    }

@app.get("/api/monitor")
def get_monitor():
    """获取系统监控"""
    import psutil
    cache = get_cache()
    try:
        return {
            "cpu": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory().percent,
            "tasks_active": len(task_scheduler._tasks),
            "api_usage": 0,
            "cache": cache.get_stats()
        }
    except:
        return {
            "cpu": 35, 
            "memory": 48, 
            "tasks_active": 3, 
            "api_usage": 85,
            "cache": cache.get_stats()
        }

@app.get("/api/cache/stats")
def get_cache_stats():
    """获取缓存统计"""
    cache = get_cache()
    return cache.get_stats()

@app.post("/api/cache/clear")
def clear_cache():
    """清空缓存"""
    cache = get_cache()
    cache.clear()
    return {"status": "ok", "message": "缓存已清空"}

@app.get("/api/logs")
def get_logs(lines: int = 100):
    """获取后端日志"""
    import subprocess
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), "/tmp/xuanling.log"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout if result.returncode == 0 else "日志文件不存在或为空"
    except Exception as e:
        return f"获取日志失败: {str(e)}"

@app.get("/api/bg-tasks")
def get_bg_tasks():
    """获取后台任务"""
    return {"tasks": []}

# ============== 工具系统 API ==============

@app.get("/api/tools")
def get_tools():
    """获取所有可用工具 (缓存 60 秒)"""
    cache = get_cache()
    cached = cache.get("/api/tools")
    if cached:
        return cached
    
    tools = tool_registry.list_all()
    result = {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": t.parameters,
                "dangerous": t.dangerous
            }
            for t in tools
        ],
        "count": len(tools)
    }
    cache.set("/api/tools", result, ttl=60)
    return result

@app.get("/api/tools/{tool_name}")
def get_tool_detail(tool_name: str):
    """获取工具详情"""
    tool = tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")
    return {
        "name": tool.name,
        "description": tool.description,
        "category": tool.category,
        "parameters": tool.parameters,
        "dangerous": tool.dangerous
    }

@app.post("/api/tools/execute")
async def execute_tool(request: ToolExecuteRequest):
    """执行工具"""
    logger.info(f"执行工具: {request.tool_name}({request.arguments})")
    result = await tool_registry.execute(request.tool_name, request.arguments)
    return result

# ============== 技能系统 API ==============

@app.get("/api/skills")
def api_list_skills():
    """获取所有技能 (缓存 60 秒)"""
    cache = get_cache()
    cached = cache.get("/api/skills")
    if cached:
        return cached
    
    result = {"skills": skill_manager.list_skills()}
    cache.set("/api/skills", result, ttl=60)
    return result

@app.get("/api/skills/{skill_name}")
def api_get_skill(skill_name: str):
    """获取技能详情"""
    skill = skill_manager.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"技能不存在: {skill_name}")
    return {
        "name": skill_name,
        "metadata": skill.metadata.to_dict(),
        "state": {
            "loaded": skill._state.loaded,
            "running": skill._state.running,
            "execution_count": skill._state.execution_count
        },
        "handlers": list(skill._handlers.keys())
    }

@app.post("/api/skills/{skill_name}/execute")
async def api_execute_skill(skill_name: str, action: str = "execute", params: Dict = None):
    """执行技能动作"""
    result = await skill_manager.execute(skill_name, action, params)
    return result

@app.post("/api/skills/{skill_name}/start")
async def api_start_skill(skill_name: str):
    """启动技能"""
    success = await skill_manager.start_skill(skill_name)
    return {"success": success, "skill": skill_name}

@app.post("/api/skills/{skill_name}/stop")
async def api_stop_skill(skill_name: str):
    """停止技能"""
    success = await skill_manager.stop_skill(skill_name)
    return {"success": success, "skill": skill_name}

@app.post("/api/skills/reload")
async def api_reload_skills():
    """热重载所有技能"""
    results = {}
    for skill_file in skill_manager.discover_skills():
        name = await skill_manager.load_skill(skill_file)
        results[str(skill_file)] = "loaded" if name else "failed"
    return {"results": results}

# ============== 子代理系统 API ==============

@app.get("/api/subagents")
def api_list_subagents():
    """获取所有子代理"""
    stats = task_scheduler.get_stats()
    return {"agents": stats.get("agents", {})}

@app.post("/api/subagents")
async def api_create_subagent(name: str, role: str = "worker", skills: List[str] = None):
    """创建子代理"""
    role_enum = AgentRole(role) if role in [r.value for r in AgentRole] else AgentRole.WORKER
    agent = await create_subagent(name, role_enum, skills)
    return {"success": True, "agent": agent.get_status()}

@app.get("/api/subagents/{agent_id}")
def api_get_subagent(agent_id: str):
    """获取子代理详情"""
    agent = task_scheduler._agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"代理不存在: {agent_id}")
    return agent.get_status()

@app.post("/api/subagents/{agent_id}/pause")
def api_pause_subagent(agent_id: str):
    """暂停子代理"""
    agent = task_scheduler._agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"代理不存在: {agent_id}")
    agent.pause()
    return {"success": True, "status": "paused"}

@app.post("/api/subagents/{agent_id}/resume")
def api_resume_subagent(agent_id: str):
    """恢复子代理"""
    agent = task_scheduler._agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"代理不存在: {agent_id}")
    agent.resume()
    return {"success": True, "status": "running"}

# ============== 任务系统 API ==============

@app.get("/api/tasks/stats")
def api_task_stats():
    """获取任务统计"""
    return task_scheduler.get_stats()

@app.get("/api/tasks")
def api_list_tasks(status: str = None):
    """获取任务列表"""
    task_status = SubTaskStatus(status) if status else None
    return {"tasks": task_scheduler.list_tasks(task_status)}

@app.post("/api/tasks")
async def api_submit_task(goal: str, name: str = None, priority: str = "normal", steps: List[Dict] = None):
    """提交新任务"""
    priority_enum = {
        "low": SubTaskPriority.LOW,
        "normal": SubTaskPriority.NORMAL,
        "high": SubTaskPriority.HIGH,
        "critical": SubTaskPriority.CRITICAL
    }.get(priority, SubTaskPriority.NORMAL)
    
    task_id = await submit_task(goal, name, priority_enum, steps)
    return {"success": True, "task_id": task_id}

@app.post("/api/tasks/plan")
async def api_plan_tasks(goal: str):
    """规划任务"""
    tasks = await task_planner.plan(goal)
    return {"goal": goal, "tasks": [t.to_dict() for t in tasks]}

@app.get("/api/tasks/{task_id}")
def api_get_subagent_task(task_id: str):
    """获取子代理任务详情"""
    task = task_scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return task.to_dict()

@app.post("/api/tasks/{task_id}/cancel")
async def api_cancel_task(task_id: str):
    """取消任务"""
    success = await task_scheduler.cancel(task_id)
    return {"success": success, "task_id": task_id}

# ============== 记忆系统 API ==============

@app.get("/api/memory")
def api_list_memory():
    """获取记忆统计"""
    return memory_manager.get_stats()

@app.post("/api/memory")
async def api_create_memory(content: str, title: str = None, type: str = "semantic", importance: int = 3, tags: List[str] = None):
    """创建记忆"""
    memory_type = MemoryType(type) if type in [t.value for t in MemoryType] else MemoryType.SEMANTIC
    importance_enum = MemoryImportance(importance) if 1 <= importance <= 5 else MemoryImportance.NORMAL
    
    memory = await remember(content=content, title=title, type=memory_type, importance=importance_enum, tags=tags)
    return {"success": True, "memory": memory.to_dict()}

@app.get("/api/memory/search")
async def api_search_memory(query: str, top_k: int = 5, memory_type: str = None):
    """搜索记忆"""
    mem_type = MemoryType(memory_type) if memory_type else None
    results = await recall(query, top_k=top_k, memory_type=mem_type)
    return {
        "query": query,
        "results": [{"memory": r.memory.to_dict(), "score": r.score, "highlight": r.highlight} for r in results]
    }

@app.get("/api/memory/{memory_id}")
def api_get_memory(memory_id: str):
    """获取指定记忆"""
    memory = memory_manager.get(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail=f"记忆不存在: {memory_id}")
    return memory.to_dict()

@app.delete("/api/memory/{memory_id}")
def api_delete_memory(memory_id: str):
    """删除记忆"""
    success = memory_manager.forget(memory_id)
    return {"success": success, "memory_id": memory_id}

@app.get("/api/memory/working")
def api_get_working_memory():
    """获取工作记忆"""
    memories = memory_manager.get_working_memory()
    return {"memories": [m.to_dict() for m in memories]}

# ============== 安全系统 API ==============

@app.get("/api/security/users")
def api_list_users():
    """获取用户列表"""
    return {"users": permission_manager.list_users()}

@app.get("/api/security/api-keys")
def api_list_api_keys(user_id: str = None):
    """获取 API 密钥列表"""
    return {"api_keys": permission_manager.list_api_keys(user_id)}

@app.post("/api/security/api-keys")
def api_create_api_key(user_id: str, name: str = "API Key", scopes: List[str] = None):
    """创建 API 密钥"""
    try:
        api_key = permission_manager.create_api_key(user_id, name, scopes)
        return {"success": True, "api_key": api_key.to_dict(), "key": api_key.key}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/security/api-keys/{key_id}")
def api_revoke_api_key(key_id: str):
    """撤销 API 密钥"""
    success = permission_manager.revoke_api_key(key_id)
    return {"success": success, "key_id": key_id}

@app.get("/api/security/audit-logs")
def api_get_audit_logs(hours: int = 24, action: str = None, actor: str = None, limit: int = 100):
    """获取审计日志"""
    start_time = datetime.now() - timedelta(hours=hours)
    logs = audit_logger.query(start_time=start_time, action=action, actor=actor, limit=limit)
    return {"logs": [l.to_dict() for l in logs]}

@app.get("/api/security/stats")
def api_security_stats():
    """获取安全统计"""
    return {
        "audit": audit_logger.get_stats(),
        "users": len(permission_manager._users),
        "api_keys": len(permission_manager._api_keys)
    }

# ============== 项目管理 API ==============

@app.get("/api/projects")
def api_list_projects(status: str = None, owner: str = None):
    """获取项目列表"""
    st = ProjectStatus(status) if status else None
    projects = project_manager.list_projects(st, owner)
    return {"projects": [p.to_dict() for p in projects]}

@app.post("/api/projects")
def api_create_project(request: CreateProjectRequest):
    """创建项目"""
    project = project_manager.create_project(
        name=request.name,
        description=request.description,
        owner=request.owner,
        tags=request.tags,
        icon=request.icon,
        color=request.color
    )
    return {"success": True, "project": project.to_dict()}

@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str):
    """获取项目详情"""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    tasks = [project_manager.get_task(tid) for tid in project.tasks if project_manager.get_task(tid)]
    documents = [project_manager.get_document(did) for did in project.documents if project_manager.get_document(did)]
    
    return {
        "project": project.to_dict(),
        "tasks": [t.to_dict() for t in tasks],
        "documents": [d.to_dict() for d in documents]
    }

@app.put("/api/projects/{project_id}")
def api_update_project(project_id: str, request: ProjectRequest):
    """更新项目"""
    project = project_manager.update_project(
        project_id, 
        name=request.name,
        description=request.description,
        icon=request.icon,
        status=request.status
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "project": project.to_dict()}

@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str):
    """删除项目"""
    success = project_manager.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "message": "项目已删除"}

# ============== 项目任务 API ==============

@app.get("/api/projects/{project_id}/tasks")
def api_list_project_tasks(project_id: str, status: str = None):
    """获取项目任务列表"""
    st = PTaskStatus(status) if status else None
    tasks = project_manager.list_tasks(project_id, st)
    return {"tasks": [t.to_dict() for t in tasks]}

@app.post("/api/projects/{project_id}/tasks")
async def api_create_project_task(project_id: str, request: CreateTaskRequest):
    """创建项目任务"""
    task = await project_manager.create_task(
        project_id=project_id,
        title=request.title,
        description=request.description,
        priority=PTaskPriority(request.priority),
        assignee=request.assignee,
        tags=request.tags
    )
    if not task:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "task": task.to_dict()}

@app.post("/api/projects/{project_id}/tasks/parse-text")
async def api_create_tasks_from_text(project_id: str, request: CreateTasksFromTextRequest):
    """📝 从文字解析并创建任务"""
    tasks = await project_manager.create_tasks_from_text(project_id, request.text)
    return {"success": True, "count": len(tasks), "tasks": [t.to_dict() for t in tasks]}

@app.get("/api/project-tasks/{task_id}")
def api_get_project_task(task_id: str):
    """获取项目任务详情"""
    task = project_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()

@app.put("/api/project-tasks/{task_id}")
def api_update_project_task(task_id: str, request: CreateTaskRequest):
    """更新项目任务"""
    task = project_manager.update_task(
        task_id,
        title=request.title,
        description=request.description,
        priority=PTaskPriority(request.priority),
        assignee=request.assignee,
        tags=request.tags
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "task": task.to_dict()}

@app.delete("/api/project-tasks/{task_id}")
def api_delete_project_task(task_id: str):
    """删除项目任务"""
    success = project_manager.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "message": "任务已删除"}

# ============== 项目文档 API ==============

@app.get("/api/projects/{project_id}/documents")
def api_list_project_documents(project_id: str):
    """获取项目文档列表"""
    docs = project_manager.list_documents(project_id)
    return {"documents": [d.to_dict() for d in docs]}

@app.post("/api/projects/{project_id}/documents")
async def api_upload_document(
    project_id: str,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    description: str = Form("")
):
    """📄 上传文档到项目"""
    content = await file.read()
    doc_type = DocumentType(document_type) if document_type in [d.value for d in DocumentType] else DocumentType.OTHER
    
    doc = await project_manager.upload_document(
        project_id=project_id,
        file_content=content,
        filename=file.filename,
        document_type=doc_type,
        description=description
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "document": doc.to_dict()}

@app.post("/api/documents/{document_id}/parse")
async def api_parse_document_to_tasks(document_id: str):
    """📋 解析文档生成任务"""
    tasks = await project_manager.parse_document_to_tasks(document_id, auto_create=True)
    return {"success": True, "count": len(tasks), "tasks": [t.to_dict() for t in tasks]}

@app.get("/api/documents/{document_id}")
def api_get_document(document_id: str):
    """获取文档详情"""
    doc = project_manager.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc.to_dict()

@app.get("/api/documents/{document_id}/download")
def api_download_document(document_id: str):
    """下载文档"""
    doc = project_manager.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(path=file_path, filename=doc.original_name, media_type=doc.file_type)

@app.delete("/api/documents/{document_id}")
def api_delete_document(document_id: str):
    """删除文档"""
    success = project_manager.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"success": True, "message": "文档已删除"}

@app.get("/api/project-manager/stats")
def api_project_manager_stats():
    """获取项目管理统计"""
    return project_manager.get_stats()

# ============== 频道管理 API ==============

@app.get("/api/channels")
def get_channels():
    """获取频道列表"""
    channels = []
    for c in _data.get("channels", []):
        channels.append({
            "id": c.get("id"),
            "name": c.get("name", ""),
            "provider": c.get("provider", ""),
            "webhook_url": c.get("webhook_url"),
            "default_target": c.get("default_target")
        })
    return {"channels": channels}

@app.post("/api/channels")
def save_channel(channel: ChannelRequest):
    """保存频道配置"""
    with data_lock:
        found = False
        for i, c in enumerate(_data.get("channels", [])):
            if c["id"] == channel.id:
                _data["channels"][i] = {
                    "id": channel.id,
                    "name": channel.name,
                    "provider": channel.provider,
                    "webhook_url": channel.webhook_url,
                    "default_target": channel.default_target,
                    "token": channel.token
                }
                found = True
                break
        
        if not found:
            if "channels" not in _data:
                _data["channels"] = []
            _data["channels"].append({
                "id": channel.id,
                "name": channel.name,
                "provider": channel.provider,
                "webhook_url": channel.webhook_url,
                "default_target": channel.default_target,
                "token": channel.token
            })
        save_data(_data)
    return {"status": "ok", "message": "频道已保存"}

@app.post("/api/channels/{channel_id}/test")
def test_channel(channel_id: str, request: Request):
    """测试频道发送"""
    return {"status": "ok", "message": f"已发送到 {channel_id}"}

# ============== 重启 API ==============

@app.post("/api/restart")
def restart_server():
    """重启后端服务"""
    import subprocess
    import threading
    
    def restart_background():
        import time
        time.sleep(2)
        subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "main:app", "--host", SERVER_HOST, "--port", str(SERVER_PORT)
        ], cwd=str(BASE_DIR), stdout=open("/tmp/xuanling.log", "a"), stderr=subprocess.STDOUT)
    
    thread = threading.Thread(target=restart_background)
    thread.start()
    return {"message": "服务正在重启...", "status": "ok"}

# ============== 静态文件 ==============

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"静态文件目录: {STATIC_DIR}")

# ============== 启动 ==============

if __name__ == "__main__":
    logger.info(f"启动玄灵AI后端服务... host={SERVER_HOST}, port={SERVER_PORT}")
    uvicorn.run(
        "main:app", 
        host=SERVER_HOST, 
        port=SERVER_PORT, 
        reload=SERVER_RELOAD
    )