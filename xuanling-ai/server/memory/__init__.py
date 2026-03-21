"""
玄灵AI 记忆系统 - 向量化语义搜索
支持短期记忆、长期记忆、语义检索、记忆衰减
"""
import os
import json
import uuid
import logging
import asyncio
import threading
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math

logger = logging.getLogger("玄灵AI.Memory")

# ============== 枚举定义 ==============

class MemoryType(Enum):
    """记忆类型"""
    EPISODIC = "episodic"      # 情景记忆 - 特定事件
    SEMANTIC = "semantic"      # 语义记忆 - 事实知识
    PROCEDURAL = "procedural"  # 程序记忆 - 技能方法
    WORKING = "working"        # 工作记忆 - 临时信息

class MemoryImportance(Enum):
    """记忆重要性"""
    TRIVIAL = 1      # 琐碎
    LOW = 2          # 低
    NORMAL = 3       # 普通
    HIGH = 4         # 高
    CRITICAL = 5     # 关键


# ============== 数据模型 ==============

@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    title: Optional[str] = None
    type: MemoryType = MemoryType.SEMANTIC
    importance: MemoryImportance = MemoryImportance.NORMAL
    embedding: Optional[List[float]] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    decay_factor: float = 1.0  # 记忆衰减因子
    source: Optional[str] = None  # 来源（对话/文档/用户输入）
    project_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "title": self.title,
            "type": self.type.value,
            "importance": self.importance.value,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "source": self.source,
            "project_id": self.project_id
        }
    
    def compute_strength(self) -> float:
        """计算记忆强度（考虑衰减、访问频率、重要性）"""
        # 时间衰减
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        time_decay = math.exp(-age_hours / (24 * 7))  # 一周半衰期
        
        # 访问强化
        access_boost = min(1.0 + self.access_count * 0.1, 3.0)
        
        # 重要性权重
        importance_weight = self.importance.value / 3.0
        
        return time_decay * access_boost * importance_weight * self.decay_factor


@dataclass
class SearchResult:
    """搜索结果"""
    memory: MemoryEntry
    score: float
    highlight: Optional[str] = None


# ============== 向量嵌入器 ==============

class EmbeddingEngine:
    """向量嵌入引擎"""
    
    def __init__(self, model: str = "text-embedding", api_key: str = None, api_url: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.api_url = api_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
        self._dimension = 1536  # 默认向量维度
        self._cache: Dict[str, List[float]] = {}
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    async def embed(self, text: str) -> List[float]:
        """生成文本向量"""
        # 检查缓存
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 调用 API
        if not self.api_key or self.api_key == "test-key":
            # 模拟向量
            return self._mock_embed(text)
        
        try:
            import aiohttp
            
            # MiniMax embedding API
            endpoint = f"{self.api_url}/embeddings"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "input": text
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=payload, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embedding = data.get("data", [{}])[0].get("embedding", [])
                        if embedding:
                            self._dimension = len(embedding)
                            self._cache[cache_key] = embedding
                            return embedding
                    else:
                        logger.error(f"Embedding API 错误: {resp.status}")
                        return self._mock_embed(text)
                        
        except Exception as e:
            logger.error(f"Embedding 失败: {e}")
            return self._mock_embed(text)
    
    def _mock_embed(self, text: str) -> List[float]:
        """模拟向量（用于无 API 时）"""
        # 使用简单的哈希模拟向量
        text_hash = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(0, 64, 4):
            val = int.from_bytes(text_hash[i:i+4], 'big')
            vector.append((val % 1000 - 500) / 500.0)
        # 扩展到目标维度
        while len(vector) < self._dimension:
            vector.extend(vector[:min(len(vector), self._dimension - len(vector))])
        return vector[:self._dimension]
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量"""
        return [await self.embed(text) for text in texts]


# ============== 向量存储 ==============

class VectorStore:
    """向量存储 - 内存版（生产环境可用 Milvus/Pinecone/Chroma）"""
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self._vectors: Dict[str, List[float]] = {}  # id -> vector
        self._metadata: Dict[str, Dict] = {}  # id -> metadata
        self._lock = threading.Lock()
    
    async def insert(self, id: str, vector: List[float], metadata: Dict = None):
        """插入向量"""
        if len(vector) != self.dimension:
            # 自动调整维度
            if len(vector) < self.dimension:
                vector = vector + [0.0] * (self.dimension - len(vector))
            else:
                vector = vector[:self.dimension]
        
        with self._lock:
            self._vectors[id] = vector
            self._metadata[id] = metadata or {}
    
    async def delete(self, id: str):
        """删除向量"""
        with self._lock:
            self._vectors.pop(id, None)
            self._metadata.pop(id, None)
    
    async def search(
        self, 
        query_vector: List[float], 
        top_k: int = 10,
        filter_func: Callable[[Dict], bool] = None
    ) -> List[Tuple[str, float, Dict]]:
        """
        搜索最相似的向量
        
        Returns:
            List of (id, similarity, metadata)
        """
        if len(query_vector) != self.dimension:
            if len(query_vector) < self.dimension:
                query_vector = query_vector + [0.0] * (self.dimension - len(query_vector))
            else:
                query_vector = query_vector[:self.dimension]
        
        # 计算余弦相似度
        results = []
        query_norm = math.sqrt(sum(x * x for x in query_vector))
        
        with self._lock:
            for id, vector in self._vectors.items():
                metadata = self._metadata.get(id, {})
                
                # 过滤
                if filter_func and not filter_func(metadata):
                    continue
                
                # 计算相似度
                dot_product = sum(a * b for a, b in zip(query_vector, vector))
                vec_norm = math.sqrt(sum(x * x for x in vector))
                
                if query_norm > 0 and vec_norm > 0:
                    similarity = dot_product / (query_norm * vec_norm)
                else:
                    similarity = 0.0
                
                results.append((id, similarity, metadata))
        
        # 排序并返回 top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "total_vectors": len(self._vectors),
            "dimension": self.dimension
        }


# ============== 记忆管理器 ==============

class MemoryManager:
    """记忆管理器"""
    
    def __init__(
        self,
        storage_path: str = None,
        embedding_engine: EmbeddingEngine = None
    ):
        self.storage_path = Path(storage_path or os.path.join(os.path.dirname(__file__), "memory_data"))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.vector_store = VectorStore(dimension=self.embedding_engine.dimension)
        
        self._memories: Dict[str, MemoryEntry] = {}
        self._short_term: List[str] = []  # 短期记忆 ID 列表（工作记忆）
        self._max_short_term = 10
        self._lock = threading.RLock()
        
        # 加载持久化数据
        self._load()
    
    def _get_memory_file(self) -> Path:
        return self.storage_path / "memories.json"
    
    def _get_vector_file(self) -> Path:
        return self.storage_path / "vectors.json"
    
    def _load(self):
        """加载记忆"""
        memory_file = self._get_memory_file()
        if memory_file.exists():
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("memories", []):
                        memory = MemoryEntry(
                            id=item.get("id"),
                            content=item.get("content", ""),
                            title=item.get("title"),
                            type=MemoryType(item.get("type", "semantic")),
                            importance=MemoryImportance(item.get("importance", 3)),
                            tags=item.get("tags", []),
                            metadata=item.get("metadata", {}),
                            created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else datetime.now(),
                            last_accessed=datetime.fromisoformat(item["last_accessed"]) if item.get("last_accessed") else datetime.now(),
                            access_count=item.get("access_count", 0),
                            source=item.get("source"),
                            project_id=item.get("project_id")
                        )
                        self._memories[memory.id] = memory
                        
                    # 加载短期记忆
                    self._short_term = data.get("short_term", [])
                    
                logger.info(f"📂 加载 {len(self._memories)} 条记忆")
            except Exception as e:
                logger.error(f"加载记忆失败: {e}")
    
    def _save(self):
        """保存记忆"""
        memory_file = self._get_memory_file()
        try:
            data = {
                "memories": [m.to_dict() for m in self._memories.values()],
                "short_term": self._short_term,
                "updated_at": datetime.now().isoformat()
            }
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")
    
    async def remember(
        self,
        content: str,
        title: str = None,
        type: MemoryType = MemoryType.SEMANTIC,
        importance: MemoryImportance = MemoryImportance.NORMAL,
        tags: List[str] = None,
        metadata: Dict = None,
        source: str = None,
        project_id: str = None
    ) -> MemoryEntry:
        """记住信息"""
        # 创建记忆条目
        memory = MemoryEntry(
            content=content,
            title=title,
            type=type,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            source=source,
            project_id=project_id
        )
        
        # 生成向量
        memory.embedding = await self.embedding_engine.embed(content)
        
        # 存储
        with self._lock:
            self._memories[memory.id] = memory
            
            # 工作记忆加入短期列表
            if type == MemoryType.WORKING:
                self._short_term.append(memory.id)
                if len(self._short_term) > self._max_short_term:
                    # 移除最老的
                    self._short_term.pop(0)
        
        # 保存到向量存储
        await self.vector_store.insert(
            memory.id,
            memory.embedding,
            {"type": memory.type.value, "tags": memory.tags, "project_id": project_id}
        )
        
        # 持久化
        self._save()
        
        logger.info(f"🧠 记住: {memory.title or content[:50]}... (ID: {memory.id})")
        return memory
    
    async def recall(
        self,
        query: str,
        top_k: int = 5,
        memory_type: MemoryType = None,
        project_id: str = None,
        min_importance: MemoryImportance = None,
        use_semantic: bool = True
    ) -> List[SearchResult]:
        """回忆信息"""
        results = []
        
        if use_semantic:
            # 语义搜索
            query_vector = await self.embedding_engine.embed(query)
            
            # 构建过滤器
            def filter_func(meta):
                if memory_type and meta.get("type") != memory_type.value:
                    return False
                if project_id and meta.get("project_id") != project_id:
                    return False
                return True
            
            vector_results = await self.vector_store.search(query_vector, top_k * 2, filter_func)
            
            for id, similarity, meta in vector_results:
                if id in self._memories:
                    memory = self._memories[id]
                    
                    # 检查重要性
                    if min_importance and memory.importance.value < min_importance.value:
                        continue
                    
                    # 计算最终分数（相似度 + 记忆强度）
                    strength = memory.compute_strength()
                    final_score = similarity * 0.7 + strength * 0.3
                    
                    results.append(SearchResult(
                        memory=memory,
                        score=final_score,
                        highlight=self._extract_highlight(query, memory.content)
                    ))
                    
                    # 更新访问
                    memory.last_accessed = datetime.now()
                    memory.access_count += 1
        else:
            # 关键词搜索
            query_lower = query.lower()
            for memory in self._memories.values():
                # 过滤
                if memory_type and memory.type != memory_type:
                    continue
                if project_id and memory.project_id != project_id:
                    continue
                if min_importance and memory.importance.value < min_importance.value:
                    continue
                
                # 简单匹配
                if query_lower in memory.content.lower() or query_lower in memory.title.lower() if memory.title else False:
                    results.append(SearchResult(
                        memory=memory,
                        score=memory.compute_strength(),
                        highlight=self._extract_highlight(query, memory.content)
                    ))
        
        # 排序并返回
        results.sort(key=lambda x: x.score, reverse=True)
        
        # 保存访问更新
        self._save()
        
        return results[:top_k]
    
    def _extract_highlight(self, query: str, content: str, context_len: int = 50) -> str:
        """提取高亮片段"""
        query_lower = query.lower()
        content_lower = content.lower()
        
        idx = content_lower.find(query_lower)
        if idx >= 0:
            start = max(0, idx - context_len)
            end = min(len(content), idx + len(query) + context_len)
            return content[start:end]
        
        return content[:context_len * 2] if len(content) > context_len * 2 else content
    
    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取指定记忆"""
        memory = self._memories.get(memory_id)
        if memory:
            memory.last_accessed = datetime.now()
            memory.access_count += 1
            self._save()
        return memory
    
    async def forget(self, memory_id: str) -> bool:
        """遗忘记忆"""
        with self._lock:
            if memory_id not in self._memories:
                return False
            
            del self._memories[memory_id]
            if memory_id in self._short_term:
                self._short_term.remove(memory_id)
            
            self._save()
        
        # 从向量存储删除（在锁外执行异步操作）
        await self.vector_store.delete(memory_id)
        logger.info(f"🗑️ 遗忘记忆: {memory_id}")
        return True
    
    def update(self, memory_id: str, **kwargs) -> Optional[MemoryEntry]:
        """更新记忆"""
        memory = self._memories.get(memory_id)
        if not memory:
            return None
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(memory, key):
                setattr(memory, key, value)
        
        # 如果内容变化，重新生成向量
        if "content" in kwargs:
            async def update_vector():
                memory.embedding = await self.embedding_engine.embed(memory.content)
                await self.vector_store.insert(memory_id, memory.embedding)
            asyncio.create_task(update_vector())
        
        self._save()
        return memory
    
    def get_working_memory(self) -> List[MemoryEntry]:
        """获取工作记忆"""
        return [self._memories[id] for id in self._short_term if id in self._memories]
    
    def clear_working_memory(self):
        """清空工作记忆"""
        with self._lock:
            for id in self._short_term:
                if id in self._memories:
                    del self._memories[id]
            self._short_term.clear()
            self._save()
    
    def decay_memories(self, threshold: float = 0.1):
        """衰减并清理弱记忆"""
        to_forget = []
        
        for id, memory in self._memories.items():
            memory.decay_factor *= 0.99  # 每次衰减 1%
            if memory.compute_strength() < threshold and memory.importance != MemoryImportance.CRITICAL:
                to_forget.append(id)
        
        for id in to_forget:
            self.forget(id)
        
        if to_forget:
            logger.info(f"🧹 清理 {len(to_forget)} 条弱记忆")
    
    def get_stats(self) -> Dict:
        """获取统计"""
        type_counts = {}
        for t in MemoryType:
            type_counts[t.value] = len([m for m in self._memories.values() if m.type == t])
        
        return {
            "total_memories": len(self._memories),
            "working_memory": len(self._short_term),
            "by_type": type_counts,
            "vector_store": self.vector_store.get_stats()
        }
    
    def export_memories(self, project_id: str = None) -> List[Dict]:
        """导出记忆"""
        memories = list(self._memories.values())
        if project_id:
            memories = [m for m in memories if m.project_id == project_id]
        return [m.to_dict() for m in memories]
    
    async def import_memories(self, memories: List[Dict]) -> int:
        """导入记忆"""
        count = 0
        for item in memories:
            try:
                memory = await self.remember(
                    content=item.get("content", ""),
                    title=item.get("title"),
                    type=MemoryType(item.get("type", "semantic")),
                    importance=MemoryImportance(item.get("importance", 3)),
                    tags=item.get("tags", []),
                    metadata=item.get("metadata", {}),
                    source=item.get("source"),
                    project_id=item.get("project_id")
                )
                count += 1
            except Exception as e:
                logger.error(f"导入记忆失败: {e}")
        
        return count


# ============== 全局实例 ==============

memory_manager = MemoryManager()


# ============== 便捷函数 ==============

async def remember(content: str, **kwargs) -> MemoryEntry:
    """记住信息"""
    return await memory_manager.remember(content, **kwargs)

async def recall(query: str, **kwargs) -> List[SearchResult]:
    """回忆信息"""
    return await memory_manager.recall(query, **kwargs)

async def forget(memory_id: str) -> bool:
    """遗忘记忆"""
    return await memory_manager.forget(memory_id)