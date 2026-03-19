"""
Memory - 记忆系统
"""
from typing import List, Dict, Any, Optional
import time
import json
import hashlib


class MemoryItem:
    """记忆项"""
    
    def __init__(self, id: str, content: str, memory_type: str = "long_term",
                 tags: List[str] = None, importance: int = 1):
        self.id = id
        self.content = content
        self.memory_type = memory_type  # "short_term", "long_term", "important"
        self.tags = tags or []
        self.importance = importance
        self.created_at = time.time()
        self.access_count = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.memory_type,
            "tags": self.tags,
            "importance": self.importance,
            "created_at": self.created_at,
            "access_count": self.access_count
        }


class ShortTermMemory:
    """短期记忆"""
    
    def __init__(self, limit: int = 20):
        self.limit = limit
        self.items: List[MemoryItem] = []
    
    def add(self, user: str, assistant: str):
        """添加对话"""
        content = f"用户: {user}\n助手: {assistant}"
        item = MemoryItem(
            id=self._gen_id(content),
            content=content,
            memory_type="short_term"
        )
        self.items.append(item)
        
        # 超过限制则移除最旧的
        if len(self.items) > self.limit:
            self.items.pop(0)
    
    def get_all(self) -> List[Dict]:
        """获取所有"""
        return [item.to_dict() for item in self.items]
    
    def clear(self):
        """清空"""
        self.items.clear()
    
    def _gen_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:8]


class LongTermMemory:
    """长期记忆"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def add(self, title: str, content: str, tags: List[str] = None, 
                  importance: int = 1) -> MemoryItem:
        """添加记忆"""
        item = MemoryItem(
            id=self._gen_id(title + content),
            content=f"{title}\n{content}",
            memory_type="long_term",
            tags=tags,
            importance=importance
        )
        await self.storage.save_memory(item)
        return item
    
    async def search(self, query: str) -> List[MemoryItem]:
        """搜索记忆"""
        return await self.storage.search_memories(query)
    
    async def get_all(self) -> List[MemoryItem]:
        """获取所有"""
        return await self.storage.get_all_memories()
    
    async def delete(self, memory_id: str):
        """删除记忆"""
        await self.storage.delete_memory(memory_id)
    
    def _gen_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:16]


class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        self.short_term = ShortTermMemory(
            limit=self.config.get("short_term_limit", 20)
        )
        
        # 长期记忆需要 storage，会在 init 时注入
        self.long_term = None
        self.storage = None
    
    async def init(self, storage):
        """初始化"""
        self.storage = storage
        self.long_term = LongTermMemory(storage)
    
    def add_turn(self, user: str, assistant: str):
        """添加对话轮次"""
        self.short_term.add(user, assistant)
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """获取最近记忆"""
        return self.short_term.get_all()[-limit:]
    
    async def add_memory(self, title: str, content: str, 
                       tags: List[str] = None, importance: int = 1) -> MemoryItem:
        """添加长期记忆"""
        if self.long_term:
            return await self.long_term.add(title, content, tags, importance)
        return None
    
    async def search_memories(self, query: str) -> List[MemoryItem]:
        """搜索记忆"""
        if self.long_term:
            return await self.long_term.search(query)
        return []
    
    async def get_all_memories(self) -> List[MemoryItem]:
        """获取所有记忆"""
        if self.long_term:
            return await self.long_term.get_all()
        return []
    
    async def delete_memory(self, memory_id: str):
        """删除记忆"""
        if self.long_term:
            await self.long_term.delete(memory_id)
    
    def clear_short_term(self):
        """清空短期记忆"""
        self.short_term.clear()
