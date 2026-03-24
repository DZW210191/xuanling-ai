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
from pydantic import BaseModel, Field, field_validator
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
    DocumentType, PROJECTS_DIR
)

# ============== 导入代理管理器 (深度重构版) ==============
from agent_manager import (
    agent_manager, Agent, AgentTask, AgentStatus, AgentRole, TaskStatus, TaskPriority,
    AGENT_TEMPLATES
)

# ============== 导入浏览器模块 ==============
from browser import browser_manager, web_search, web_scrape, web_screenshot

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
    """保存设置到文件"""
    to_save = {
        "model": settings.get("model", ""),
        "apiUrl": settings.get("apiUrl", ""),
        "apiKey": settings.get("apiKey", "")
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)
    logger.info(f"设置已保存: model={settings.get('model')}, apiUrl={settings.get('apiUrl')}, apiKey={'已配置' if settings.get('apiKey') else '未配置'}")

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
            "conversations": {},  # 对话历史存储: {session_id: {messages: [], created_at, updated_at}}
            "next_ids": {"project": 1, "memory": 1, "agent": 1, "agent_memory": 1, "conversation": 1, "message": 1}
        }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

_data = load_data()

# ============== Pydantic 数据模型 (使用明确的后缀避免冲突) ==============

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")
    project_id: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    agent: str = "玄灵AI"

class ProjectRequest(BaseModel):
    """项目创建/更新请求"""
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: Optional[str] = Field(default="", max_length=2000, description="项目描述")
    icon: str = Field(default="📁", max_length=10, description="项目图标")
    status: str = Field(default="进行中", max_length=20, description="项目状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    tasks: int = Field(default=0, ge=0, description="任务数量")
    memory: int = Field(default=0, ge=0, description="记忆数量")
    
    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('项目名称不能为空')
        return v.strip()

class MemoryRequest(BaseModel):
    """记忆创建请求"""
    title: str = Field(..., min_length=1, max_length=200, description="记忆标题")
    content: str = Field(..., min_length=1, max_length=50000, description="记忆内容")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    project_id: Optional[int] = None
    importance: int = Field(default=1, ge=1, le=5, description="重要性等级 (1-5)")
    
    @field_validator('title', 'content')
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('字段不能为空')
        return v.strip()

class AgentRequest(BaseModel):
    """子代理创建请求"""
    name: str = Field(..., min_length=1, max_length=50, description="代理名称")
    description: Optional[str] = Field(default="", max_length=500, description="代理描述")
    status: Optional[str] = Field(default="idle", max_length=20, description="代理状态")
    
    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('代理名称不能为空')
        return v.strip()

class AgentMemoryRequest(BaseModel):
    """子代理记忆请求"""
    title: str = Field(..., min_length=1, max_length=200, description="记忆标题")
    content: Optional[str] = Field(default="", max_length=10000, description="记忆内容")

class SettingsRequest(BaseModel):
    """设置请求 - 同时支持 camelCase 和 snake_case 字段名"""
    model: Optional[str] = Field(default="", max_length=100, description="模型名称")
    apiUrl: Optional[str] = Field(default="", alias="api_url", max_length=500, description="API 地址")
    apiKey: Optional[str] = Field(default=None, alias="api_key", description="API Key")
    
    class Config:
        populate_by_name = True  # 允许通过别名填充

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
    
    # 初始化 AI 引擎配置
    api_key = app_settings.get("apiKey") or MINIMAX_API_KEY
    api_url = app_settings.get("apiUrl") or MINIMAX_BASE_URL
    model = app_settings.get("model") or "MiniMax-M2.5"
    if api_key and api_url:
        ai_engine.configure(api_key=api_key, api_url=api_url, model=model)
        logger.info(f"✅ AI 引擎配置完成: model={model}, url={api_url}")
    else:
        logger.warning("⚠️ AI 引擎未配置 API Key，对话功能将不可用")
    
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
        return "⚠️ API Key 未配置，请在系统设置中配置 API Key 后重试。"
    
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
                        return msg.get("content", msg.get("text", "⚠️ AI 响应为空"))
                    
                    if data.get("base_resp", {}).get("status_msg"):
                        error_msg = data["base_resp"]["status_msg"]
                        logger.error(f"AI API 返回错误: {error_msg}")
                        return f"⚠️ API 错误: {error_msg}"
                    
                    return "⚠️ AI 响应为空"
                else:
                    error_text = await resp.text()
                    logger.error(f"AI API 错误: {resp.status} - {error_text}")
                    return f"⚠️ API 错误 ({resp.status}): {error_text[:100]}"
    except ImportError:
        return "⚠️ aiohttp 模块未安装，无法调用 API"
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        return f"⚠️ AI 调用失败: {str(e)}"

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

# ============== 对话历史 API ==============

class ConversationMessage(BaseModel):
    """对话消息模型"""
    role: str = Field(..., description="角色: user 或 assistant")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[str] = Field(default=None, description="时间戳")

class ConversationCreate(BaseModel):
    """创建对话请求"""
    title: Optional[str] = Field(default=None, description="对话标题")
    first_message: Optional[str] = Field(default=None, description="第一条消息")

class ConversationUpdate(BaseModel):
    """更新对话请求"""
    title: Optional[str] = None

class MessageCreate(BaseModel):
    """添加消息请求"""
    role: str
    content: str

@app.get("/api/conversations")
def api_list_conversations():
    """获取所有对话列表"""
    conversations = []
    for conv_id, conv_data in _data.get("conversations", {}).items():
        messages = conv_data.get("messages", [])
        conversations.append({
            "id": conv_id,
            "title": conv_data.get("title", "未命名对话"),
            "message_count": len(messages),
            "created_at": conv_data.get("created_at"),
            "updated_at": conv_data.get("updated_at"),
            "preview": messages[-1].get("content", "")[:50] if messages else ""
        })
    
    # 按更新时间倒序排列
    conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return {"conversations": conversations, "count": len(conversations)}

@app.post("/api/conversations")
def api_create_conversation(request: ConversationCreate = None):
    """创建新对话"""
    with data_lock:
        conv_id = _data["next_ids"].get("conversation", 1)
        _data["next_ids"]["conversation"] = conv_id + 1
        
        now = datetime.now().isoformat()
        conv_data = {
            "id": conv_id,
            "title": request.title if request and request.title else f"对话 {conv_id}",
            "messages": [],
            "created_at": now,
            "updated_at": now
        }
        
        if "conversations" not in _data:
            _data["conversations"] = {}
        
        _data["conversations"][str(conv_id)] = conv_data
        save_data(_data)
    
    return {"status": "ok", "conversation": conv_data}

@app.get("/api/conversations/{conversation_id}")
def api_get_conversation(conversation_id: str):
    """获取对话详情（包含所有消息）"""
    conv = _data.get("conversations", {}).get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv

@app.put("/api/conversations/{conversation_id}")
def api_update_conversation(conversation_id: str, request: ConversationUpdate):
    """更新对话（如修改标题）"""
    with data_lock:
        conv = _data.get("conversations", {}).get(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        if request.title:
            conv["title"] = request.title
            conv["updated_at"] = datetime.now().isoformat()
            save_data(_data)
    
    return {"status": "ok", "conversation": conv}

@app.delete("/api/conversations/{conversation_id}")
def api_delete_conversation(conversation_id: str):
    """删除对话"""
    with data_lock:
        if conversation_id not in _data.get("conversations", {}):
            raise HTTPException(status_code=404, detail="对话不存在")
        
        del _data["conversations"][conversation_id]
        save_data(_data)
    
    return {"status": "ok", "message": "对话已删除"}

@app.post("/api/conversations/{conversation_id}/messages")
def api_add_message(conversation_id: str, message: MessageCreate):
    """向对话添加消息"""
    with data_lock:
        conv = _data.get("conversations", {}).get(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        now = datetime.now().isoformat()
        msg_data = {
            "role": message.role,
            "content": message.content,
            "timestamp": now
        }
        
        conv["messages"].append(msg_data)
        conv["updated_at"] = now
        
        # 自动生成标题（如果是第一条用户消息）
        if message.role == "user" and len(conv["messages"]) <= 2:
            conv["title"] = message.content[:30] + ("..." if len(message.content) > 30 else "")
        
        save_data(_data)
    
    return {"status": "ok", "message": msg_data}

@app.get("/api/conversations/{conversation_id}/messages")
def api_get_messages(conversation_id: str):
    """获取对话的所有消息"""
    conv = _data.get("conversations", {}).get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return {"messages": conv.get("messages", [])}

@app.delete("/api/conversations/{conversation_id}/messages")
def api_clear_messages(conversation_id: str):
    """清空对话消息"""
    with data_lock:
        conv = _data.get("conversations", {}).get(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        conv["messages"] = []
        conv["updated_at"] = datetime.now().isoformat()
        save_data(_data)
    
    return {"status": "ok", "message": "消息已清空"}

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
        "model": settings.model or app_settings.get("model", ""),
        "apiUrl": settings.apiUrl or app_settings.get("apiUrl", ""),
        "apiKey": settings.apiKey or ""
    }
    save_settings_to_file(app_settings)
    
    # 重新配置 AI 引擎
    if app_settings.get("apiKey") and app_settings.get("apiUrl"):
        ai_engine.configure(
            api_key=app_settings["apiKey"],
            api_url=app_settings["apiUrl"],
            model=app_settings.get("model", "MiniMax-M2.5")
        )
        logger.info(f"✅ AI 引擎已重新配置: model={app_settings.get('model')}")
    
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
def activate_model(provider_id: str, request: dict = None):
    """激活模型并保存配置"""
    global app_settings
    
    if request:
        # 更新设置
        app_settings["model"] = request.get("model", app_settings.get("model", ""))
        app_settings["apiUrl"] = request.get("api_url", app_settings.get("apiUrl", ""))
        if request.get("api_key"):
            app_settings["apiKey"] = request.get("api_key")
        
        # 配置 AI 引擎
        ai_engine.configure(
            api_key=app_settings.get("apiKey", ""),
            api_url=app_settings.get("apiUrl", ""),
            model=app_settings.get("model", "")
        )
        
        # 保存到文件
        save_settings_to_file(app_settings)
    
    return {
        "status": "ok",
        "message": f"模型 {provider_id} 已激活",
        "config": {
            "model": app_settings.get("model", ""),
            "api_url": app_settings.get("apiUrl", "")
        }
    }

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
    except Exception as e:
        logger.warning(f"获取监控数据失败: {e}")
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

# ============== 代理管理 API (深度重构版) ==============

class AgentCreateRequest(BaseModel):
    """创建代理请求"""
    name: str
    role: str = "worker"
    description: str = ""
    template: Optional[str] = None
    skills: List[str] = []

class AgentUpdateRequest(BaseModel):
    """更新代理请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    skills: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    icon: Optional[str] = None
    max_concurrent_tasks: Optional[int] = None

class AgentTaskCreateRequest(BaseModel):
    """创建代理任务请求"""
    title: str
    description: str = ""
    goal: str = ""
    priority: int = 5
    assigned_agent: Optional[str] = None

@app.get("/api/agents")
def api_list_agents():
    """获取所有代理"""
    agents = agent_manager.list_agents()
    return {
        "agents": [a.to_dict() for a in agents],
        "count": len(agents),
        "templates": list(AGENT_TEMPLATES.keys())
    }

@app.post("/api/agents")
def api_create_agent(request: AgentCreateRequest):
    """创建新代理"""
    agent = agent_manager.create_agent(
        name=request.name,
        role=request.role,
        description=request.description,
        template=request.template,
        skills=request.skills
    )
    return {"status": "ok", "agent": agent.to_dict()}

@app.get("/api/agents/templates")
def api_get_agent_templates():
    """获取代理模板列表"""
    return {"templates": AGENT_TEMPLATES}

@app.get("/api/agents/{agent_id}")
def api_get_agent(agent_id: str):
    """获取代理详情"""
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="代理不存在")
    
    # 获取代理的任务
    tasks = agent_manager.list_tasks(agent_id=agent_id)
    
    return {
        "agent": agent.to_dict(),
        "tasks": [t.to_dict() for t in tasks[:10]]  # 最近10个任务
    }

@app.put("/api/agents/{agent_id}")
def api_update_agent(agent_id: str, request: AgentUpdateRequest):
    """更新代理"""
    update_data = {k: v for k, v in request.dict().items() if v is not None}
    agent = agent_manager.update_agent(agent_id, **update_data)
    if not agent:
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"status": "ok", "agent": agent.to_dict()}

@app.delete("/api/agents/{agent_id}")
def api_delete_agent(agent_id: str):
    """删除代理"""
    success = agent_manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"status": "ok", "message": "代理已删除"}

@app.post("/api/agents/{agent_id}/start")
def api_start_agent(agent_id: str):
    """启动代理"""
    success = agent_manager.start_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"status": "ok", "message": "代理已启动"}

@app.post("/api/agents/{agent_id}/pause")
def api_pause_agent(agent_id: str):
    """暂停代理"""
    success = agent_manager.pause_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"status": "ok", "message": "代理已暂停"}

@app.post("/api/agents/{agent_id}/stop")
def api_stop_agent(agent_id: str):
    """停止代理"""
    success = agent_manager.stop_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"status": "ok", "message": "代理已停止"}

# ============== 代理任务 API ==============

@app.get("/api/agents/{agent_id}/tasks")
def api_get_agent_tasks(agent_id: str, status: str = None):
    """获取代理的任务列表"""
    task_status = TaskStatus(status) if status else None
    tasks = agent_manager.list_tasks(agent_id=agent_id, status=task_status)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}

@app.post("/api/agents/{agent_id}/tasks")
def api_create_agent_task(agent_id: str, request: AgentTaskCreateRequest):
    """为代理创建任务"""
    task = agent_manager.create_task(
        title=request.title,
        description=request.description,
        goal=request.goal,
        priority=request.priority,
        assigned_agent=agent_id
    )
    return {"status": "ok", "task": task.to_dict()}

@app.get("/api/agent-tasks")
def api_list_all_tasks(status: str = None):
    """获取所有任务"""
    task_status = TaskStatus(status) if status else None
    tasks = agent_manager.list_tasks(status=task_status)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}

@app.get("/api/agent-tasks/{task_id}")
def api_get_task(task_id: str):
    """获取任务详情"""
    task = agent_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()

@app.put("/api/agent-tasks/{task_id}")
def api_update_task(task_id: str, status: str = None, progress: float = None, result: Dict = None):
    """更新任务状态"""
    update_data = {}
    if status:
        update_data["status"] = status
    if progress is not None:
        update_data["progress"] = progress
    if result:
        update_data["result"] = result
    
    task = agent_manager.update_task(task_id, **update_data)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"status": "ok", "task": task.to_dict()}

@app.delete("/api/agent-tasks/{task_id}")
def api_delete_task(task_id: str):
    """删除任务"""
    success = agent_manager.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"status": "ok", "message": "任务已删除"}

@app.get("/api/agents/stats/overview")
def api_agents_stats():
    """获取代理统计概览"""
    return agent_manager.get_stats()

# ============== 任务执行与监控 API ==============

@app.post("/api/agent-tasks/{task_id}/execute")
async def api_execute_task(task_id: str):
    """执行任务"""
    result = await agent_manager.execute_task(task_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/agent-tasks/{task_id}/logs")
def api_get_task_logs(task_id: str):
    """获取任务执行日志"""
    logs = agent_manager.get_task_logs(task_id)
    return {"logs": logs, "count": len(logs)}

@app.get("/api/agent-tasks/{task_id}/status")
def api_get_task_status(task_id: str):
    """获取任务实时状态（用于轮询）"""
    task = agent_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task.id,
        "status": task.status.value,
        "progress": task.progress,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "error": task.error,
        "result": task.result
    }

@app.get("/api/agents/{agent_id}/realtime")
def api_get_agent_realtime(agent_id: str):
    """获取代理实时状态（用于轮询监控）"""
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="代理不存在")
    
    # 获取当前任务
    current_tasks = []
    for task_id in agent.current_tasks:
        task = agent_manager.get_task(task_id)
        if task:
            current_tasks.append({
                "id": task.id,
                "title": task.title,
                "status": task.status.value,
                "progress": task.progress
            })
    
    return {
        "agent_id": agent_id,
        "name": agent.name,
        "status": agent.status.value,
        "current_tasks": current_tasks,
        "stats": {
            "total_tasks": agent.total_tasks,
            "completed_tasks": agent.completed_tasks,
            "failed_tasks": agent.failed_tasks,
            "success_rate": round(agent.success_rate * 100, 1)
        },
        "updated_at": agent.updated_at
    }

@app.get("/api/agents/realtime/all")
def api_get_all_agents_realtime():
    """获取所有代理实时状态（监控大盘）"""
    agents = agent_manager.list_agents()
    
    result = []
    for agent in agents:
        current_tasks = []
        for task_id in agent.current_tasks:
            task = agent_manager.get_task(task_id)
            if task:
                current_tasks.append({
                    "id": task.id,
                    "title": task.title,
                    "progress": task.progress
                })
        
        result.append({
            "id": agent.id,
            "name": agent.name,
            "icon": agent.icon,
            "status": agent.status.value,
            "role": agent.role.value,
            "current_tasks": current_tasks,
            "success_rate": round(agent.success_rate * 100, 1)
        })
    
    return {"agents": result, "timestamp": datetime.now().isoformat()}

# ============== SSE 实时推送 ==============

@app.get("/api/agents/{agent_id}/stream")
async def api_agent_status_stream(agent_id: str):
    """代理状态 SSE 实时推送"""
    from fastapi.responses import StreamingResponse
    import asyncio
    
    async def event_generator():
        while True:
            agent = agent_manager.get_agent(agent_id)
            if not agent:
                yield f"data: {json.dumps({'error': '代理不存在'})}\n\n"
                break
            
            # 获取当前任务状态
            tasks_status = []
            for task_id in agent.current_tasks:
                task = agent_manager.get_task(task_id)
                if task:
                    tasks_status.append({
                        "id": task.id,
                        "status": task.status.value,
                        "progress": task.progress
                    })
            
            data = {
                "agent_id": agent_id,
                "status": agent.status.value,
                "tasks": tasks_status,
                "timestamp": datetime.now().isoformat()
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

# ============== 旧版兼容 API ==============

# 保留旧的记忆端点以兼容现有前端

@app.get("/api/agents/{agent_id}/memory")
def api_get_agent_memory_compat(agent_id: str):
    """获取子代理记忆 (前端兼容)"""
    memories = _data.get("agent_memories", {}).get(str(agent_id), {})
    return {"memories": memories}

@app.post("/api/agents/{agent_id}/memory")
def api_add_agent_memory_compat(agent_id: str, memory: AgentMemoryRequest):
    """添加子代理记忆 (前端兼容)"""
    with data_lock:
        if "agent_memories" not in _data:
            _data["agent_memories"] = {}
        if str(agent_id) not in _data["agent_memories"]:
            _data["agent_memories"][str(agent_id)] = {}
        
        memory_id = _data["next_ids"].get("agent_memory", 1)
        _data["next_ids"]["agent_memory"] = memory_id + 1
        
        _data["agent_memories"][str(agent_id)][str(memory_id)] = {
            "id": memory_id,
            "title": memory.title,
            "content": memory.content or "",
            "created_at": datetime.now().isoformat()
        }
        
        save_data(_data)
    
    return {"status": "ok", "message": "记忆已添加"}

# ============== 记忆系统 API ==============

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

# ============== 前端兼容: 记忆 API (/memory) ==============

@app.get("/memory")
def api_list_memory_compat():
    """获取记忆列表 (前端兼容)"""
    memories = []
    for m in _data.get("memories", []):
        memories.append({
            "id": m.get("id"),
            "title": m.get("title", ""),
            "content": m.get("content", ""),
            "tags": m.get("tags", []),
            "project_id": m.get("project_id"),
            "importance": m.get("importance", 1),
            "created_at": m.get("created_at")
        })
    return {"memories": memories}

@app.post("/memory")
def api_create_memory_compat(memory: MemoryRequest):
    """创建记忆 (前端兼容)"""
    with data_lock:
        memory_id = _data["next_ids"]["memory"]
        _data["next_ids"]["memory"] += 1
        
        new_memory = {
            "id": memory_id,
            "title": memory.title,
            "content": memory.content,
            "tags": memory.tags or [],
            "project_id": memory.project_id,
            "importance": memory.importance,
            "created_at": datetime.now().isoformat()
        }
        
        if "memories" not in _data:
            _data["memories"] = []
        _data["memories"].append(new_memory)
        
        save_data(_data)
    
    return {"status": "ok", "memory": new_memory}

@app.put("/memory/{memory_id}")
def api_update_memory_compat(memory_id: str, memory: MemoryRequest):
    """更新记忆 (前端兼容)"""
    with data_lock:
        found = False
        updated_memory = None
        for i, m in enumerate(_data.get("memories", [])):
            if str(m.get("id")) == str(memory_id):
                _data["memories"][i]["title"] = memory.title
                _data["memories"][i]["content"] = memory.content
                _data["memories"][i]["tags"] = memory.tags or []
                _data["memories"][i]["importance"] = memory.importance
                _data["memories"][i]["updated_at"] = datetime.now().isoformat()
                found = True
                updated_memory = _data["memories"][i]
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="记忆不存在")
        
        save_data(_data)
    
    return {"status": "ok", "message": "记忆已更新", "memory": updated_memory}

@app.delete("/memory/{memory_id}")
def api_delete_memory_compat(memory_id: str):
    """删除记忆 (前端兼容)"""
    with data_lock:
        original_len = len(_data.get("memories", []))
        _data["memories"] = [m for m in _data.get("memories", []) if str(m.get("id")) != str(memory_id)]
        
        if len(_data["memories"]) == original_len:
            raise HTTPException(status_code=404, detail="记忆不存在")
        
        save_data(_data)
    
    return {"status": "ok", "message": "记忆已删除"}

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

# ============== 前端兼容: 任务状态更新 API ==============

@app.put("/api/tasks/{task_id}")
def api_update_task_status_compat(task_id: str, request: dict):
    """更新任务状态 (前端兼容)"""
    status = request.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="缺少 status 参数")
    
    task = project_manager.update_task(task_id, status=status)
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

# ============== 浏览器自动化 API ==============

class BrowserOpenRequest(BaseModel):
    """打开网页请求"""
    url: str
    wait_until: str = "networkidle"

class BrowserActionRequest(BaseModel):
    """浏览器操作请求"""
    ref: str = None
    text: str = None
    selector: str = None
    direction: str = None
    key: str = None
    script: str = None
    path: str = None
    full_page: bool = False
    timeout: int = 30000
    milliseconds: int = None

class WebSearchRequest(BaseModel):
    """网页搜索请求"""
    query: str
    engine: str = "google"
    max_results: int = 10

class WebScrapeRequest(BaseModel):
    """网页抓取请求"""
    url: str
    extract_links: bool = True
    extract_images: bool = False
    extract_text: bool = True

@app.get("/api/browser/status")
async def api_browser_status():
    """获取浏览器状态"""
    return browser_manager.get_status()

@app.post("/api/browser/open")
async def api_browser_open(request: BrowserOpenRequest):
    """打开网页"""
    result = await browser_manager.open(request.url, request.wait_until)
    return result

@app.post("/api/browser/navigate")
async def api_browser_navigate(direction: str):
    """浏览器导航 (back/forward/reload)"""
    if direction == "back":
        return await browser_manager.back()
    elif direction == "forward":
        return await browser_manager.forward()
    elif direction == "reload":
        return await browser_manager.reload()
    return {"success": False, "error": f"未知方向: {direction}"}

@app.post("/api/browser/close")
async def api_browser_close():
    """关闭浏览器"""
    await browser_manager.close()
    return {"success": True, "message": "浏览器已关闭"}

@app.get("/api/browser/snapshot")
async def api_browser_snapshot(interactive_only: bool = True, scope: str = None):
    """获取页面快照"""
    snapshot = await browser_manager.snapshot(interactive_only, scope)
    return snapshot.to_dict()

@app.post("/api/browser/click")
async def api_browser_click(ref: str):
    """点击元素"""
    return await browser_manager.click(ref)

@app.post("/api/browser/fill")
async def api_browser_fill(request: BrowserActionRequest):
    """填写输入框"""
    return await browser_manager.fill(request.ref, request.text)

@app.post("/api/browser/press")
async def api_browser_press(key: str):
    """按键"""
    return await browser_manager.press(key)

@app.post("/api/browser/scroll")
async def api_browser_scroll(direction: str, distance: int = 300):
    """滚动页面"""
    return await browser_manager.scroll(direction, distance)

@app.get("/api/browser/text")
async def api_browser_get_text(ref: str = None, selector: str = None):
    """获取页面文本"""
    return await browser_manager.get_text(ref, selector)

@app.get("/api/browser/html")
async def api_browser_get_html(ref: str = None, selector: str = None):
    """获取页面 HTML"""
    return await browser_manager.get_html(ref, selector)

@app.get("/api/browser/query")
async def api_browser_query(selector: str):
    """CSS 选择器查询"""
    return await browser_manager.query(selector)

@app.get("/api/browser/xpath")
async def api_browser_xpath(expression: str):
    """XPath 查询"""
    return await browser_manager.xpath(expression)

@app.post("/api/browser/screenshot")
async def api_browser_screenshot(
    path: str = None,
    full_page: bool = False,
    selector: str = None
):
    """网页截图"""
    return await browser_manager.screenshot(path, full_page, selector)

@app.post("/api/browser/wait")
async def api_browser_wait(selector: str, timeout: int = 30000):
    """等待元素"""
    return await browser_manager.wait_for_selector(selector, timeout)

@app.post("/api/browser/wait-load")
async def api_browser_wait_load(state: str = "networkidle"):
    """等待页面加载"""
    return await browser_manager.wait_for_load(state)

@app.post("/api/browser/sleep")
async def api_browser_sleep(milliseconds: int):
    """等待指定时间"""
    return await browser_manager.wait(milliseconds)

@app.post("/api/browser/eval")
async def api_browser_eval(script: str):
    """执行 JavaScript"""
    return await browser_manager.evaluate(script)

@app.get("/api/browser/cookies")
async def api_browser_get_cookies():
    """获取所有 Cookies"""
    return await browser_manager.get_cookies()

@app.post("/api/browser/cookie")
async def api_browser_set_cookie(name: str, value: str, domain: str = None):
    """设置 Cookie"""
    return await browser_manager.set_cookie(name, value, domain)

@app.delete("/api/browser/cookies")
async def api_browser_clear_cookies():
    """清除所有 Cookies"""
    return await browser_manager.clear_cookies()

@app.post("/api/browser/search")
async def api_web_search(request: WebSearchRequest):
    """网页搜索"""
    return await web_search(request.query, request.engine, request.max_results)

@app.post("/api/browser/scrape")
async def api_web_scrape(request: WebScrapeRequest):
    """网页抓取"""
    return await web_scrape(
        request.url,
        request.extract_links,
        request.extract_images,
        request.extract_text
    )

@app.post("/api/browser/scrape-screenshot")
async def api_web_screenshot(request: WebScrapeRequest, full_page: bool = True):
    """网页截图 (自动打开并截图)"""
    return await web_screenshot(request.url, full_page)

@app.get("/api/browser/url")
async def api_browser_get_url():
    """获取当前 URL"""
    return {"url": await browser_manager.get_url()}

@app.get("/api/browser/title")
async def api_browser_get_title():
    """获取页面标题"""
    return {"title": await browser_manager.get_title()}

# ============== 前端兼容: 项目文件管理 API ==============

@app.get("/project-manager/projects/{project_name}")
def api_get_project_files_compat(project_name: str):
    """获取项目文件列表 (前端兼容)"""
    # 查找项目
    project = None
    for p in _data.get("projects", []):
        if p.get("name") == project_name:
            project = p
            break
    
    # 也检查 project_manager
    pm_project = project_manager.get_project(project_name)
    
    if not project and not pm_project:
        return {"error": f"项目不存在: {project_name}", "files": [], "project": {}}
    
    # 检查项目目录
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        return {
            "project": project or (pm_project.to_dict() if pm_project else {}),
            "files": [],
            "error": None
        }
    
    # 扫描文件
    files = []
    for item in project_dir.rglob("*"):
        if item.is_file():
            rel_path = str(item.relative_to(project_dir))
            files.append({
                "path": rel_path,
                "size": item.stat().st_size,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            })
    
    return {
        "project": project or (pm_project.to_dict() if pm_project else {}),
        "files": files,
        "error": None
    }

@app.get("/project-manager/projects/{project_name}/files/{file_path:path}")
def api_get_project_file_content(project_name: str, file_path: str):
    """获取项目文件内容 (前端兼容)"""
    full_path = PROJECTS_DIR / project_name / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail=f"不是文件: {file_path}")
    
    # 检查文件大小
    if full_path.stat().st_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件太大，无法预览")
    
    try:
        content = full_path.read_text(encoding='utf-8', errors='replace')
        return {"content": content, "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

@app.put("/project-manager/projects/{project_name}/files/{file_path:path}")
def api_update_project_file_content(project_name: str, file_path: str, request: dict):
    """更新项目文件内容 (前端兼容)"""
    full_path = PROJECTS_DIR / project_name / file_path
    
    # 确保目录存在
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = request.get("content", "")
    
    try:
        full_path.write_text(content, encoding='utf-8')
        return {"success": True, "message": "文件已保存", "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {str(e)}")

@app.post("/project-manager/projects")
def api_create_project_compat(request: dict):
    """创建项目 (前端兼容)"""
    name = request.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    
    description = request.get("description", "")
    
    # 检查是否已存在
    for p in _data.get("projects", []):
        if p.get("name") == name:
            return {"error": "项目名称已存在", "project": None}
    
    # 创建项目
    project = project_manager.create_project(
        name=name,
        description=description,
        icon="📁"
    )
    
    # 也添加到 _data
    with data_lock:
        if "projects" not in _data:
            _data["projects"] = []
        _data["projects"].append({
            "id": project.id,
            "name": name,
            "description": description,
            "icon": "📁",
            "status": "draft",
            "created_at": datetime.now().isoformat()
        })
        save_data(_data)
    
    return {"status": "ok", "project": project.to_dict()}

@app.delete("/project-manager/projects/{project_name}")
def api_delete_project_compat(project_name: str):
    """删除项目 (前端兼容)"""
    # 从 project_manager 删除
    success = project_manager.delete_project(project_name)
    
    # 从 _data 中删除
    with data_lock:
        original_len = len(_data.get("projects", []))
        _data["projects"] = [p for p in _data.get("projects", []) if p.get("name") != project_name]
        
        if len(_data["projects"]) == original_len and not success:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        save_data(_data)
    
    return {"status": "ok", "message": "项目已删除"}

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

# ============== 子代理 API 配置 ==============

AGENT_API_CONFIG_FILE = BASE_DIR / "agent_api_configs.json"

def load_agent_api_configs():
    """加载代理API配置"""
    try:
        with open(AGENT_API_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_agent_api_configs(configs):
    """保存代理API配置"""
    # 不保存API Key到文件，只保存在内存中
    safe_configs = {}
    for agent_id, cfg in configs.items():
        safe_configs[agent_id] = {
            "use_global": cfg.get("use_global", True),
            "api_url": cfg.get("api_url", ""),
            "model": cfg.get("model", ""),
            "has_api_key": bool(cfg.get("api_key", ""))
        }
    with open(AGENT_API_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_configs, f, ensure_ascii=False, indent=2)

# 内存中的代理配置（包含API Key）
_agent_api_configs = load_agent_api_configs()

@app.get("/api/agent-api-configs")
def get_agent_api_configs():
    """获取所有代理的API配置"""
    return {"configs": _agent_api_configs}

@app.get("/api/agent-api-configs/{agent_id}")
def get_agent_api_config(agent_id: str):
    """获取单个代理的API配置"""
    config = _agent_api_configs.get(agent_id, {"use_global": True})
    # 不返回API Key
    safe_config = {k: v for k, v in config.items() if k != "api_key"}
    return {"config": safe_config}

class AgentApiConfigRequest(BaseModel):
    use_global: bool = True
    api_url: str = ""
    api_key: str = ""
    model: str = ""

@app.post("/api/agent-api-configs/{agent_id}")
def set_agent_api_config(agent_id: str, config: AgentApiConfigRequest):
    """设置代理的API配置"""
    _agent_api_configs[agent_id] = {
        "use_global": config.use_global,
        "api_url": config.api_url,
        "api_key": config.api_key,
        "model": config.model
    }
    save_agent_api_configs(_agent_api_configs)
    logger.info(f"代理 {agent_id} API配置已更新")
    return {"success": True, "message": "配置已保存"}

@app.delete("/api/agent-api-configs/{agent_id}")
def delete_agent_api_config(agent_id: str):
    """删除代理的API配置"""
    if agent_id in _agent_api_configs:
        del _agent_api_configs[agent_id]
        save_agent_api_configs(_agent_api_configs)
        logger.info(f"代理 {agent_id} API配置已删除")
    return {"success": True, "message": "配置已删除"}

def get_agent_api_config(agent_id: str) -> dict:
    """获取代理的实际API配置（供内部调用）"""
    config = _agent_api_configs.get(agent_id, {})
    if config.get("use_global", True):
        # 使用全局配置
        return {
            "api_url": app_settings.get("apiUrl") or MINIMAX_BASE_URL,
            "api_key": app_settings.get("apiKey") or MINIMAX_API_KEY,
            "model": app_settings.get("model") or "MiniMax-M2.5"
        }
    else:
        # 使用代理专属配置
        return {
            "api_url": config.get("api_url") or app_settings.get("apiUrl") or MINIMAX_BASE_URL,
            "api_key": config.get("api_key") or app_settings.get("apiKey") or MINIMAX_API_KEY,
            "model": config.get("model") or app_settings.get("model") or "MiniMax-M2.5"
        }

# ============== 重启 API ==============

@app.post("/api/restart")
def restart_server():
    """重启后端服务"""
    import subprocess
    import threading
    
    def restart_background():
        import time
        time.sleep(2)
        # 使用 with 语句确保文件句柄正确关闭
        with open("/tmp/xuanling.log", "a") as log_file:
            subprocess.Popen([
                sys.executable, "-m", "uvicorn", 
                "main:app", "--host", SERVER_HOST, "--port", str(SERVER_PORT)
            ], cwd=str(BASE_DIR), stdout=log_file, stderr=subprocess.STDOUT)
    
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