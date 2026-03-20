"""
玄灵AI 后端 - FastAPI 主入口 (增强版)
修复: 数据持久化、安全性、异常处理、真实AI对接
"""
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

# ============== 日志配置 ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("玄灵AI")

# ============== 配置 ==============
# 从环境变量读取，生产环境请配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

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
    name: str
    description: Optional[str] = ""
    icon: str = "📁"
    status: str = "进行中"
    progress: int = 0
    tasks: int = 0
    memory: int = 0

class Memory(BaseModel):
    id: Optional[int] = None
    title: str
    content: str
    tags: List[str] = []
    project_id: Optional[int] = None
    importance: int = 1

# ============== 真实 AI 对接 (MiniMax) ==============

async def call_minimax_ai(user_message: str) -> str:
    """调用 MiniMax AI API"""
    if not MINIMAX_API_KEY:
        logger.warning("未配置 MINIMAX_API_KEY，使用模拟回复")
        return await mock_ai_response(user_message)
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "MiniMax-M2.5",
                "messages": [
                    {"role": "system", "content": "你是玄灵AI，一个友好、聪明的AI助手。"},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            headers = {
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json"
            }
            async with session.post(
                f"{MINIMAX_BASE_URL}/text/chatcompletion_v2",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "抱歉，AI 响应为空")
                else:
                    logger.error(f"AI API 错误: {resp.status}")
                    return await mock_ai_response(user_message)
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
    """健康检查"""
    return {
        "message": "玄灵AI API", 
        "version": "1.1.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

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

@app.get("/api/projects")
def get_projects_list():
    """获取项目列表"""
    return get_projects()

@app.post("/api/projects")
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
            "icon": project.icon,
            "status": project.status,
            "progress": project.progress,
            "tasks": project.tasks,
            "memory": project.memory,
            "created_at": datetime.now().isoformat()
        }
        _data["projects"].append(new_project)
        save_data(_data)
    
    return new_project

@app.put("/api/projects/{project_id}")
def update_project(project_id: int, project: Project):
    """更新项目"""
    logger.info(f"更新项目: {project_id}")
    
    with data_lock:
        for i, p in enumerate(_data["projects"]):
            if p["id"] == project_id:
                _data["projects"][i].update({
                    "name": project.name,
                    "description": project.description or "",
                    "icon": project.icon,
                    "status": project.status,
                    "progress": project.progress,
                    "tasks": project.tasks,
                    "memory": project.memory,
                    "updated_at": datetime.now().isoformat()
                })
                save_data(_data)
                return _data["projects"][i]
    
    raise HTTPException(status_code=404, detail="项目不存在")

@app.delete("/api/projects/{project_id}")
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

# ============== 启动 ==============

if __name__ == "__main__":
    logger.info("启动玄灵AI后端服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
