"""
玄灵AI 安全系统 - 权限控制和审计日志
支持 RBAC、API 密钥管理、审计追踪、安全策略
"""
import os
import json
import uuid
import logging
import asyncio
import threading
import hashlib
import secrets
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps

logger = logging.getLogger("玄灵AI.Security")

# ============== 枚举定义 ==============

class Permission(Enum):
    """权限枚举"""
    # 系统权限
    ADMIN = "admin"                    # 管理员权限
    READ_CONFIG = "read_config"        # 读取配置
    WRITE_CONFIG = "write_config"      # 写入配置
    
    # 工具权限
    READ_FILE = "read_file"            # 读取文件
    WRITE_FILE = "write_file"          # 写入文件
    EXEC_COMMAND = "exec_command"      # 执行命令
    NETWORK_ACCESS = "network_access"  # 网络访问
    
    # 技能权限
    USE_SKILL = "use_skill"            # 使用技能
    MANAGE_SKILL = "manage_skill"      # 管理技能
    
    # 代理权限
    CREATE_AGENT = "create_agent"      # 创建代理
    MANAGE_AGENT = "manage_agent"      # 管理代理
    
    # 记忆权限
    READ_MEMORY = "read_memory"        # 读取记忆
    WRITE_MEMORY = "write_memory"      # 写入记忆
    
    # 审计权限
    VIEW_AUDIT = "view_audit"          # 查看审计日志
    EXPORT_DATA = "export_data"        # 导出数据

class Role(Enum):
    """角色枚举"""
    ADMIN = "admin"           # 管理员 - 全部权限
    USER = "user"             # 普通用户 - 基本权限
    GUEST = "guest"           # 访客 - 只读权限
    AGENT = "agent"           # 代理 - 执行权限
    SERVICE = "service"       # 服务账户 - API 权限

class AuditAction(Enum):
    """审计动作"""
    # 认证
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    
    # 数据操作
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    
    # 系统操作
    CONFIG_CHANGE = "config_change"
    SKILL_LOAD = "skill_load"
    SKILL_UNLOAD = "skill_unload"
    SKILL_EXECUTE = "skill_execute"
    
    # 代理操作
    AGENT_CREATE = "agent_create"
    AGENT_EXECUTE = "agent_execute"
    
    # 安全事件
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


# ============== 数据模型 ==============

@dataclass
class User:
    """用户"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    username: str = ""
    email: Optional[str] = None
    display_name: Optional[str] = None
    roles: List[Role] = field(default_factory=lambda: [Role.USER])
    permissions: Set[Permission] = field(default_factory=set)
    api_keys: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: Permission) -> bool:
        """检查是否有权限"""
        if Permission.ADMIN in self.permissions:
            return True
        return permission in self.permissions
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "roles": [r.value for r in self.roles],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


@dataclass
class APIKey:
    """API 密钥"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    name: str = ""
    user_id: str = ""
    scopes: List[str] = field(default_factory=list)  # 权限范围
    rate_limit: int = 100  # 每分钟请求数
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    is_active: bool = True
    
    def is_valid(self) -> bool:
        """检查是否有效"""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key[:8] + "..." + self.key[-4:],
            "user_id": self.user_id,
            "scopes": self.scopes,
            "rate_limit": self.rate_limit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None
        }


@dataclass
class AuditLog:
    """审计日志"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    action: str = ""  # AuditAction 或自定义动作
    actor: str = ""  # 用户 ID 或系统
    actor_type: str = "user"  # user / system / agent
    resource: str = ""  # 资源标识
    resource_type: str = ""  # 资源类型
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"  # success / failure / denied
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "resource": self.resource,
            "resource_type": self.resource_type,
            "details": self.details,
            "ip_address": self.ip_address,
            "status": self.status,
            "error_message": self.error_message
        }


# ============== 角色权限映射 ==============

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # 所有权限
    
    Role.USER: {
        Permission.READ_FILE,
        Permission.WRITE_FILE,
        Permission.READ_MEMORY,
        Permission.WRITE_MEMORY,
        Permission.USE_SKILL,
        Permission.CREATE_AGENT,
    },
    
    Role.GUEST: {
        Permission.READ_FILE,
        Permission.READ_MEMORY,
    },
    
    Role.AGENT: {
        Permission.READ_FILE,
        Permission.WRITE_FILE,
        Permission.EXEC_COMMAND,
        Permission.NETWORK_ACCESS,
        Permission.USE_SKILL,
        Permission.READ_MEMORY,
        Permission.WRITE_MEMORY,
    },
    
    Role.SERVICE: {
        Permission.READ_FILE,
        Permission.WRITE_FILE,
        Permission.READ_MEMORY,
        Permission.WRITE_MEMORY,
        Permission.USE_SKILL,
        Permission.CREATE_AGENT,
        Permission.MANAGE_AGENT,
    },
}


# ============== 安全策略 ==============

@dataclass
class SecurityPolicy:
    """安全策略"""
    # 密码策略
    min_password_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special: bool = False
    password_expiry_days: int = 90
    
    # API 密钥策略
    api_key_expiry_days: int = 365
    max_api_keys_per_user: int = 5
    
    # 会话策略
    session_timeout_minutes: int = 60
    max_concurrent_sessions: int = 5
    
    # 速率限制
    default_rate_limit: int = 100  # 每分钟
    burst_limit: int = 20  # 突发限制
    
    # 审计策略
    audit_all_actions: bool = True
    audit_retention_days: int = 90
    audit_sensitive_only: bool = False
    
    # 敏感操作
    sensitive_actions: List[str] = field(default_factory=lambda: [
        "write_file", "exec_command", "delete", "config_change"
    ])
    
    # IP 白名单
    ip_whitelist: List[str] = field(default_factory=list)
    
    # 禁止的命令模式
    forbidden_command_patterns: List[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/",
        r"mkfs",
        r"dd\s+if=.*of=/dev/",
        r">\s*/dev/sd",
        r"chmod\s+777",
        r"curl.*\|\s*bash",
        r"wget.*\|\s*bash",
    ])


# ============== 权限管理器 ==============

class PermissionManager:
    """权限管理器"""
    
    def __init__(self, policy: SecurityPolicy = None):
        self.policy = policy or SecurityPolicy()
        self._users: Dict[str, User] = {}
        self._api_keys: Dict[str, APIKey] = {}
        self._role_permissions = ROLE_PERMISSIONS.copy()
        self._lock = threading.RLock()
        
        # 创建默认管理员
        self._create_default_admin()
    
    def _create_default_admin(self):
        """创建默认管理员"""
        admin_id = "admin"
        if admin_id not in self._users:
            admin_key = APIKey(
                name="Default Admin Key",
                user_id=admin_id,
                scopes=["admin"]
            )
            
            admin = User(
                id=admin_id,
                username="admin",
                display_name="Administrator",
                roles=[Role.ADMIN],
                permissions=set(Permission),
                api_keys=[admin_key.id]
            )
            
            self._users[admin_id] = admin
            self._api_keys[admin_key.id] = admin_key
            
            # 安全：不在日志中打印完整的 API Key
            logger.info(f"👤 创建默认管理员 (API Key 前缀: {admin_key.key[:8]}...)")
    
    def create_user(
        self,
        username: str,
        roles: List[Role] = None,
        email: str = None,
        display_name: str = None
    ) -> User:
        """创建用户"""
        with self._lock:
            # 检查用户名是否已存在
            if any(u.username == username for u in self._users.values()):
                raise ValueError(f"用户名已存在: {username}")
            
            roles = roles or [Role.USER]
            permissions = set()
            for role in roles:
                permissions.update(self._role_permissions.get(role, set()))
            
            user = User(
                username=username,
                email=email,
                display_name=display_name or username,
                roles=roles,
                permissions=permissions
            )
            
            self._users[user.id] = user
            logger.info(f"👤 创建用户: {username} (角色: {[r.value for r in roles]})")
            
            return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        return self._users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        for user in self._users.values():
            if user.username == username:
                return user
        return None
    
    def create_api_key(
        self,
        user_id: str,
        name: str = "API Key",
        scopes: List[str] = None,
        expires_days: int = None
    ) -> APIKey:
        """创建 API 密钥"""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                raise ValueError(f"用户不存在: {user_id}")
            
            if len(user.api_keys) >= self.policy.max_api_keys_per_user:
                raise ValueError(f"已达到最大 API 密钥数量: {self.policy.max_api_keys_per_user}")
            
            expires_at = None
            if expires_days:
                expires_at = datetime.now() + timedelta(days=expires_days)
            elif self.policy.api_key_expiry_days:
                expires_at = datetime.now() + timedelta(days=self.policy.api_key_expiry_days)
            
            api_key = APIKey(
                name=name,
                user_id=user_id,
                scopes=scopes or [],
                expires_at=expires_at
            )
            
            self._api_keys[api_key.id] = api_key
            user.api_keys.append(api_key.id)
            
            logger.info(f"🔑 创建 API 密钥: {name} (用户: {user.username})")
            
            return api_key
    
    def validate_api_key(self, key: str) -> Optional[User]:
        """验证 API 密钥"""
        for api_key in self._api_keys.values():
            if api_key.key == key and api_key.is_valid():
                api_key.last_used = datetime.now()
                return self._users.get(api_key.user_id)
        return None
    
    def revoke_api_key(self, key_id: str) -> bool:
        """撤销 API 密钥"""
        with self._lock:
            if key_id not in self._api_keys:
                return False
            
            api_key = self._api_keys[key_id]
            api_key.is_active = False
            
            user = self._users.get(api_key.user_id)
            if user and key_id in user.api_keys:
                user.api_keys.remove(key_id)
            
            logger.info(f"🚫 撤销 API 密钥: {api_key.name}")
            return True
    
    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """检查权限"""
        user = self._users.get(user_id)
        if not user:
            return False
        return user.has_permission(permission)
    
    def grant_permission(self, user_id: str, permission: Permission) -> bool:
        """授予权限"""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return False
            user.permissions.add(permission)
            logger.info(f"✅ 授权: {user.username} -> {permission.value}")
            return True
    
    def revoke_permission(self, user_id: str, permission: Permission) -> bool:
        """撤销权限"""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return False
            user.permissions.discard(permission)
            logger.info(f"🚫 撤权: {user.username} -> {permission.value}")
            return True
    
    def check_command(self, command: str) -> Tuple[bool, str]:
        """检查命令是否安全"""
        for pattern in self.policy.forbidden_command_patterns:
            if re.search(pattern, command):
                return False, f"禁止执行危险命令 (匹配: {pattern})"
        return True, ""
    
    def is_sensitive_action(self, action: str) -> bool:
        """判断是否敏感操作"""
        return action in self.policy.sensitive_actions
    
    def list_users(self) -> List[Dict]:
        """列出用户"""
        return [u.to_dict() for u in self._users.values()]
    
    def list_api_keys(self, user_id: str = None) -> List[Dict]:
        """列出 API 密钥"""
        keys = self._api_keys.values()
        if user_id:
            keys = [k for k in keys if k.user_id == user_id]
        return [k.to_dict() for k in keys]


# ============== 审计日志管理器 ==============

class AuditLogger:
    """审计日志管理器"""
    
    def __init__(self, storage_path: str = None, policy: SecurityPolicy = None):
        self.storage_path = Path(storage_path or os.path.join(os.path.dirname(__file__), "audit_logs"))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.policy = policy or SecurityPolicy()
        
        self._logs: List[AuditLog] = []
        self._lock = threading.Lock()
        self._current_file: Optional[Path] = None
        
        # 加载今日日志
        self._load_today()
    
    def _get_log_file(self, date: datetime = None) -> Path:
        """获取日志文件路径"""
        date = date or datetime.now()
        return self.storage_path / f"audit_{date.strftime('%Y-%m-%d')}.jsonl"
    
    def _load_today(self):
        """加载今日日志"""
        log_file = self._get_log_file()
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            log = AuditLog(
                                id=data.get("id"),
                                timestamp=datetime.fromisoformat(data["timestamp"]),
                                action=data.get("action", ""),
                                actor=data.get("actor", ""),
                                actor_type=data.get("actor_type", "user"),
                                resource=data.get("resource", ""),
                                resource_type=data.get("resource_type", ""),
                                details=data.get("details", {}),
                                ip_address=data.get("ip_address"),
                                status=data.get("status", "success"),
                                error_message=data.get("error_message")
                            )
                            self._logs.append(log)
                logger.info(f"📂 加载审计日志: {len(self._logs)} 条")
            except Exception as e:
                logger.error(f"加载审计日志失败: {e}")
    
    async def log(
        self,
        action: str,
        resource: str = "",
        resource_type: str = "",
        actor: str = "system",
        actor_type: str = "system",
        details: Dict = None,
        ip_address: str = None,
        user_agent: str = None,
        status: str = "success",
        error_message: str = None
    ) -> AuditLog:
        """记录审计日志"""
        # 检查是否需要记录
        if self.policy.audit_sensitive_only and not self._is_sensitive(action):
            return None
        
        log = AuditLog(
            action=action,
            resource=resource,
            resource_type=resource_type,
            actor=actor,
            actor_type=actor_type,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
        
        with self._lock:
            self._logs.append(log)
            
            # 写入文件
            log_file = self._get_log_file()
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')
        
        # 敏感操作警告
        if self._is_sensitive(action):
            logger.warning(f"⚠️ 敏感操作: {action} by {actor} on {resource}")
        
        return log
    
    def _is_sensitive(self, action: str) -> bool:
        """判断是否敏感操作"""
        return action in self.policy.sensitive_actions
    
    def query(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        actor: str = None,
        action: str = None,
        resource: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """查询审计日志"""
        results = []
        
        for log in reversed(self._logs):
            # 过滤条件
            if start_time and log.timestamp < start_time:
                continue
            if end_time and log.timestamp > end_time:
                continue
            if actor and log.actor != actor:
                continue
            if action and log.action != action:
                continue
            if resource and log.resource != resource:
                continue
            if status and log.status != status:
                continue
            
            results.append(log)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_stats(self, hours: int = 24) -> Dict:
        """获取统计"""
        start = datetime.now() - timedelta(hours=hours)
        
        logs = [l for l in self._logs if l.timestamp >= start]
        
        action_counts = {}
        status_counts = {"success": 0, "failure": 0, "denied": 0}
        actor_counts = {}
        
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
            status_counts[log.status] = status_counts.get(log.status, 0) + 1
            actor_counts[log.actor] = actor_counts.get(log.actor, 0) + 1
        
        return {
            "total_logs": len(logs),
            "by_action": action_counts,
            "by_status": status_counts,
            "by_actor": actor_counts,
            "time_range_hours": hours
        }
    
    def cleanup(self, days: int = None):
        """清理旧日志"""
        days = days or self.policy.audit_retention_days
        cutoff = datetime.now() - timedelta(days=days)
        
        # 清理内存中的旧日志
        self._logs = [l for l in self._logs if l.timestamp >= cutoff]
        
        # 清理文件
        for file in self.storage_path.glob("audit_*.jsonl"):
            try:
                date_str = file.stem.split('_')[1]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                if file_date < cutoff:
                    file.unlink()
                    logger.info(f"🧹 删除旧审计日志: {file.name}")
            except:
                pass


# ============== 速率限制器 ==============

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, policy: SecurityPolicy = None):
        self.policy = policy or SecurityPolicy()
        self._requests: Dict[str, List[datetime]] = {}  # key -> timestamps
        self._lock = threading.Lock()
    
    def check(self, key: str, limit: int = None) -> Tuple[bool, int]:
        """
        检查速率限制
        
        Returns:
            (allowed, remaining)
        """
        limit = limit or self.policy.default_rate_limit
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        with self._lock:
            # 清理旧请求
            if key in self._requests:
                self._requests[key] = [t for t in self._requests[key] if t > minute_ago]
            else:
                self._requests[key] = []
            
            # 检查限制
            current_count = len(self._requests[key])
            
            if current_count >= limit:
                return False, 0
            
            # 记录请求
            self._requests[key].append(now)
            
            return True, limit - current_count - 1
    
    def reset(self, key: str):
        """重置限制"""
        with self._lock:
            self._requests.pop(key, None)


# ============== 安全中间件 ==============

class SecurityMiddleware:
    """安全中间件 - 用于 FastAPI"""
    
    def __init__(
        self,
        permission_manager: PermissionManager = None,
        audit_logger: AuditLogger = None,
        rate_limiter: RateLimiter = None
    ):
        self.permission_manager = permission_manager or PermissionManager()
        self.audit_logger = audit_logger or AuditLogger()
        self.rate_limiter = rate_limiter or RateLimiter()
    
    async def authenticate(self, api_key: str) -> Optional[User]:
        """认证"""
        user = self.permission_manager.validate_api_key(api_key)
        if user:
            user.last_login = datetime.now()
        return user
    
    async def authorize(self, user: User, permission: Permission) -> bool:
        """授权检查"""
        has_perm = user.has_permission(permission)
        
        if not has_perm:
            await self.audit_logger.log(
                action="permission_denied",
                actor=user.id,
                resource=permission.value,
                status="denied"
            )
        
        return has_perm
    
    async def check_rate_limit(self, key: str, limit: int = None) -> Tuple[bool, int]:
        """速率限制检查"""
        allowed, remaining = self.rate_limiter.check(key, limit)
        
        if not allowed:
            await self.audit_logger.log(
                action="rate_limit_exceeded",
                actor=key,
                status="denied"
            )
        
        return allowed, remaining
    
    async def audit(
        self,
        action: str,
        user: User,
        resource: str = "",
        details: Dict = None,
        status: str = "success"
    ):
        """记录审计日志"""
        await self.audit_logger.log(
            action=action,
            actor=user.id if user else "anonymous",
            actor_type="user" if user else "anonymous",
            resource=resource,
            details=details,
            status=status
        )


# ============== 装饰器 ==============

def require_permission(permission: Permission):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User = None, **kwargs):
            if not user or not user.has_permission(permission):
                raise PermissionError(f"需要权限: {permission.value}")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def audit_action(action: str):
    """审计装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User = None, **kwargs):
            result = await func(*args, user=user, **kwargs)
            
            # 记录审计日志
            if hasattr(wrapper, '_audit_logger'):
                await wrapper._audit_logger.log(
                    action=action,
                    actor=user.id if user else "system",
                    status="success"
                )
            
            return result
        return wrapper
    return decorator


# ============== 全局实例 ==============

security_policy = SecurityPolicy()
permission_manager = PermissionManager(security_policy)
audit_logger = AuditLogger(policy=security_policy)
rate_limiter = RateLimiter(security_policy)
security_middleware = SecurityMiddleware(
    permission_manager,
    audit_logger,
    rate_limiter
)


# ============== 便捷函数 ==============

def get_admin_key() -> str:
    """获取管理员 API Key (脱敏显示，仅供调试)"""
    admin = permission_manager.get_user("admin")
    if admin and admin.api_keys:
        api_key = permission_manager._api_keys.get(admin.api_keys[0])
        if api_key:
            # 安全：只返回脱敏后的密钥，不返回完整值
            return f"{api_key.key[:8]}...{api_key.key[-4:]}"
    return ""

def get_admin_key_full() -> str:
    """获取完整管理员 API Key (仅限内部使用，不要暴露给外部)"""
    admin = permission_manager.get_user("admin")
    if admin and admin.api_keys:
        api_key = permission_manager._api_keys.get(admin.api_keys[0])
        if api_key:
            return api_key.key
    return ""