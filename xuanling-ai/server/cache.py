"""
玄灵AI 缓存系统 - API 响应缓存
支持内存缓存、TTL、自动清理
"""
import time
import hashlib
import json
import threading
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from dataclasses import dataclass

logger = logging.getLogger("玄灵AI.Cache")

@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    expires_at: float
    created_at: float
    hits: int = 0


class APICache:
    """API 响应缓存"""
    
    def __init__(self, default_ttl: int = 60, max_size: int = 1000):
        """
        初始化缓存
        
        Args:
            default_ttl: 默认过期时间 (秒)
            max_size: 最大缓存条目数
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def _generate_key(self, path: str, params: Dict = None) -> str:
        """生成缓存键"""
        if params:
            param_str = json.dumps(params, sort_keys=True, default=str)
            key = f"{path}:{hashlib.md5(param_str.encode()).hexdigest()}"
        else:
            key = path
        return key
    
    def get(self, path: str, params: Dict = None) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            path: 请求路径
            params: 请求参数
            
        Returns:
            缓存值或 None
        """
        key = self._generate_key(path, params)
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            # 检查是否过期
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # 命中
            entry.hits += 1
            self._stats["hits"] += 1
            return entry.value
    
    def set(self, path: str, value: Any, ttl: int = None, params: Dict = None):
        """
        设置缓存
        
        Args:
            path: 请求路径
            value: 缓存值
            ttl: 过期时间 (秒)
            params: 请求参数
        """
        key = self._generate_key(path, params)
        ttl = ttl or self._default_ttl
        
        with self._lock:
            # 检查是否需要清理
            if len(self._cache) >= self._max_size:
                self._evict_expired()
            
            # 如果仍然满了，删除最少使用的
            if len(self._cache) >= self._max_size:
                self._evict_lru()
            
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
                created_at=time.time()
            )
    
    def delete(self, path: str, params: Dict = None):
        """删除缓存"""
        key = self._generate_key(path, params)
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            logger.info("缓存已清空")
    
    def _evict_expired(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if v.expires_at < now]
        
        for key in expired_keys:
            del self._cache[key]
            self._stats["evictions"] += 1
        
        if expired_keys:
            logger.debug(f"清理过期缓存: {len(expired_keys)} 条")
    
    def _evict_lru(self):
        """清理最少使用的缓存"""
        if not self._cache:
            return
        
        # 找到最少使用的
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].hits)
        del self._cache[lru_key]
        self._stats["evictions"] += 1
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "hit_rate": round(hit_rate, 4)
            }
    
    def invalidate_pattern(self, pattern: str):
        """
        使匹配模式的缓存失效
        
        Args:
            pattern: 路径前缀模式，如 "/api/projects"
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            
            if keys_to_delete:
                logger.debug(f"使缓存失效: {len(keys_to_delete)} 条")


def cached(ttl: int = 60, key_params: list = None):
    """
    缓存装饰器
    
    Args:
        ttl: 过期时间 (秒)
        key_params: 用于生成缓存键的参数名列表
        
    Usage:
        @cached(ttl=30)
        def get_items():
            return items
        
        @cached(ttl=60, key_params=["user_id"])
        def get_user(user_id: str):
            return user
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取缓存实例
            cache = get_cache()
            
            # 生成缓存键
            path = func.__name__
            params = {}
            
            if key_params:
                # 从 kwargs 中提取参数
                for param in key_params:
                    if param in kwargs:
                        params[param] = kwargs[param]
            
            # 尝试从缓存获取
            cached_value = cache.get(path, params if params else None)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(path, result, ttl, params if params else None)
            
            return result
        
        return wrapper
    return decorator


# 全局缓存实例
_cache_instance: Optional[APICache] = None
_cache_lock = threading.Lock()


def get_cache() -> APICache:
    """获取全局缓存实例"""
    global _cache_instance
    
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = APICache()
    
    return _cache_instance


def init_cache(default_ttl: int = 60, max_size: int = 1000) -> APICache:
    """
    初始化全局缓存
    
    Args:
        default_ttl: 默认过期时间
        max_size: 最大条目数
        
    Returns:
        缓存实例
    """
    global _cache_instance
    
    with _cache_lock:
        _cache_instance = APICache(default_ttl=default_ttl, max_size=max_size)
        logger.info(f"缓存初始化完成: default_ttl={default_ttl}s, max_size={max_size}")
    
    return _cache_instance