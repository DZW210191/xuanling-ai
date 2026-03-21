"""
玄灵AI 单元测试 - 记忆系统
"""
import pytest
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import (
    memory_manager, MemoryType, MemoryImportance,
    remember, recall, MemoryEntry
)


class TestMemoryManager:
    """记忆管理器测试"""
    
    def test_manager_exists(self):
        """测试管理器存在"""
        assert memory_manager is not None
    
    def test_get_stats(self):
        """测试获取统计"""
        stats = memory_manager.get_stats()
        assert isinstance(stats, dict)
        assert "total_memories" in stats
    
    @pytest.mark.asyncio
    async def test_remember_and_recall(self):
        """测试记忆和回忆"""
        # 记住一条信息
        memory = await remember(
            content="测试记忆内容",
            title="测试标题",
            type=MemoryType.SEMANTIC,
            importance=MemoryImportance.NORMAL
        )
        
        assert memory is not None
        assert memory.content == "测试记忆内容"
        assert memory.title == "测试标题"
        
        # 回忆
        results = await recall("测试")
        assert len(results) > 0
    
    @pytest.mark.asyncio
    async def test_memory_types(self):
        """测试不同类型的记忆"""
        for mem_type in [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]:
            memory = await remember(
                content=f"{mem_type.value} 类型测试",
                type=mem_type
            )
            assert memory.type == mem_type
    
    @pytest.mark.asyncio
    async def test_memory_importance(self):
        """测试记忆重要性"""
        for imp in [MemoryImportance.LOW, MemoryImportance.NORMAL, MemoryImportance.HIGH]:
            memory = await remember(
                content=f"重要性 {imp.value} 测试",
                importance=imp
            )
            assert memory.importance == imp
    
    @pytest.mark.asyncio
    async def test_forget_memory(self):
        """测试遗忘记忆"""
        # 创建记忆
        memory = await remember(content="将被遗忘的记忆")
        memory_id = memory.id
        
        # 验证存在
        retrieved = memory_manager.get(memory_id)
        assert retrieved is not None
        
        # 遗忘
        success = await memory_manager.forget(memory_id)
        assert success == True
        
        # 验证已删除
        retrieved = memory_manager.get(memory_id)
        assert retrieved is None
    
    def test_get_working_memory(self):
        """测试获取工作记忆"""
        memories = memory_manager.get_working_memory()
        assert isinstance(memories, list)


class TestMemoryEntry:
    """记忆条目测试"""
    
    def test_create_memory_entry(self):
        """测试创建记忆条目"""
        entry = MemoryEntry(
            id="test_id",
            content="测试内容",
            type=MemoryType.SEMANTIC,
            importance=MemoryImportance.NORMAL
        )
        
        assert entry.id == "test_id"
        assert entry.content == "测试内容"
    
    def test_memory_entry_to_dict(self):
        """测试记忆条目转字典"""
        entry = MemoryEntry(
            id="test_id",
            content="测试内容",
            type=MemoryType.SEMANTIC,
            importance=MemoryImportance.HIGH
        )
        
        data = entry.to_dict()
        assert data["id"] == "test_id"
        assert data["content"] == "测试内容"
        assert data["type"] == "semantic"
        assert data["importance"] == 4
    
    def test_compute_strength(self):
        """测试计算记忆强度"""
        entry = MemoryEntry(
            content="测试",
            importance=MemoryImportance.HIGH,
            access_count=5
        )
        
        strength = entry.compute_strength()
        # 强度可能超过 1.0，取决于重要性、访问次数等
        assert strength > 0
        assert isinstance(strength, float)


class TestMemorySearch:
    """记忆搜索测试"""
    
    @pytest.mark.asyncio
    async def test_search_by_keyword(self):
        """测试关键词搜索"""
        # 添加一些记忆
        await remember(content="Python 编程语言", title="Python")
        await remember(content="JavaScript 前端开发", title="JavaScript")
        
        # 搜索
        results = await recall("Python")
        assert len(results) > 0
    
    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """测试限制搜索结果数量"""
        # 添加多个记忆
        for i in range(5):
            await remember(content=f"搜索测试内容 {i}")
        
        # 限制返回 2 条
        results = await recall("搜索测试", top_k=2)
        assert len(results) <= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])