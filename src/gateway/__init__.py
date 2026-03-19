"""
Gateway - 消息网关
"""
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass
import time
import uuid


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
    
    @classmethod
    def create(cls, sender: str, content: str, platform: str, channel: str = "", metadata: Dict = None):
        return cls(
            id=str(uuid.uuid4()),
            sender=sender,
            content=content,
            platform=platform,
            channel=channel,
            metadata=metadata or {},
            timestamp=time.time()
        )


@dataclass
class Response:
    """响应结构"""
    message: str
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return {
            "message": self.message,
            "metadata": self.metadata or {}
        }


class RateLimiter:
    """限流器"""
    
    def __init__(self, max_requests: int = 60, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests: Dict[str, list] = {}
    
    def check(self, user_id: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # 清理过期请求
        self.requests[user_id] = [
            t for t in self.requests[user_id]
            if now - t < self.window
        ]
        
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        self.requests[user_id].append(now)
        return True


class Auth:
    """认证"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.tokens: Dict[str, Dict] = {}
    
    def verify(self, message: Message) -> bool:
        """验证消息"""
        # 简化版：默认都通过
        return True
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """验证 token"""
        return self.tokens.get(token)


class Router:
    """消息路由器"""
    
    def __init__(self):
        self.routes: Dict[str, Callable] = {}
        self.default_handler: Optional[Callable] = None
    
    def route(self, pattern: str):
        """路由装饰器"""
        def decorator(func):
            self.routes[pattern] = func
            return func
        return decorator
    
    def match(self, pattern: str, content: str) -> bool:
        """匹配路由"""
        if pattern == "*":
            return True
        return pattern in content
    
    async def handle(self, message: Message, default_handler: Callable = None) -> Response:
        """处理消息"""
        for pattern, handler in self.routes.items():
            if self.match(pattern, message.content):
                return await handler(message)
        
        if default_handler:
            return await default_handler(message)
        
        return Response(message="好的，我收到了你的消息。")


class Gateway:
    """网关"""
    
    def __init__(self, agent, plugins, config: Dict = None):
        self.agent = agent
        self.plugins = plugins
        self.config = config or {}
        
        self.router = Router()
        self.auth = Auth(config.get("auth"))
        self.rate_limiter = RateLimiter(
            max_requests=config.get("rate_limit", {}).get("max_requests", 60),
            window=config.get("rate_limit", {}).get("window", 60)
        )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.router.route("帮助")
        async def help_handler(message: Message) -> Response:
            return Response(
                message="我是玄灵AI，我能：\n"
                       "• 智能对话\n"
                       "• 管理项目\n"
                       "• 执行任务\n"
                       "• 记忆信息\n"
                       "有什么可以帮你的？"
            )
        
        @self.router.route("项目")
        async def project_handler(message: Message) -> Response:
            return Response(
                message="📁 项目管理功能：\n\n"
                       "我可以在控制台帮你管理项目，包括：\n"
                       "• 创建新项目\n"
                       "• 查看项目文件\n"
                       "• 编辑项目文档\n"
                       "• 删除项目\n\n"
                       "请打开控制台 <a href='/'>玄灵AI控制台</a> 进入「项目管理」面板操作"
            )
        
        @self.router.route("记忆")
        async def memory_handler(message: Message) -> Response:
            return Response(
                message="🧠 记忆系统功能：\n\n"
                       "我具备长期记忆能力，可以：\n"
                       "• 记住你告诉我的重要信息\n"
                       "• 记住你的偏好和习惯\n"
                       "• 记住项目相关的知识\n\n"
                       "请打开控制台 <a href='/'>玄灵AI控制台</a> 进入「记忆系统」面板查看"
            )
    
    async def handle_message(self, message: Message) -> Response:
        """处理消息"""
        # 1. 限流检查
        if not self.rate_limiter.check(message.sender):
            return Response(message="请求过于频繁，请稍后再试。")
        
        # 2. 认证检查
        if not self.auth.verify(message):
            return Response(message="认证失败")
        
        # 3. 路由处理
        response = await self.router.handle(message, self.agent.handle)
        
        # 如果是字符串，转换为 Response
        if isinstance(response, str):
            response = Response(message=response)
        
        return response
    
    async def handle_feishu(self, message: dict) -> Response:
        """处理飞书消息"""
        msg = Message.create(
            sender=message.get("sender_id", ""),
            content=message.get("content", ""),
            platform="feishu",
            channel=message.get("channel_id", ""),
            metadata=message
        )
        return await self.handle_message(msg)
    
    async def handle_telegram(self, message: dict) -> Response:
        """处理 Telegram 消息"""
        msg = Message.create(
            sender=message.get("from", {}).get("id", ""),
            content=message.get("text", ""),
            platform="telegram",
            channel=message.get("chat", {}).get("id", ""),
            metadata=message
        )
        return await self.handle_message(msg)
    
    async def handle_web(self, message: str, user_id: str = "web_user") -> Response:
        """处理 Web 消息"""
        msg = Message.create(
            sender=user_id,
            content=message,
            platform="web",
            metadata={}
        )
        return await self.handle_message(msg)
