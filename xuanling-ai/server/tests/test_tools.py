"""
玄灵AI 单元测试 - 工具系统
"""
import pytest
import sys
import asyncio
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import tool_registry, ToolDefinition


class TestToolRegistry:
    """工具注册中心测试"""
    
    def test_registry_exists(self):
        """测试注册中心存在"""
        assert tool_registry is not None
    
    def test_list_all_tools(self):
        """测试列出所有工具"""
        tools = tool_registry.list_all()
        assert len(tools) > 0
        assert all(isinstance(t, ToolDefinition) for t in tools)
    
    def test_get_tool_by_name(self):
        """测试按名称获取工具"""
        tool = tool_registry.get("read_file")
        assert tool is not None
        assert tool.name == "read_file"
    
    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        tool = tool_registry.get("nonexistent_tool")
        assert tool is None
    
    def test_tool_has_required_attributes(self):
        """测试工具有必要属性"""
        tools = tool_registry.list_all()
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'parameters')
            assert hasattr(tool, 'handler')
    
    def test_tool_schema_generation(self):
        """测试工具 Schema 生成"""
        tool = tool_registry.get("read_file")
        schema = tool.to_openai_schema()
        assert "type" in schema
        assert schema["type"] == "function"
        assert "function" in schema
        assert "name" in schema["function"]
    
    def test_list_by_category(self):
        """测试按类别列出工具"""
        file_tools = tool_registry.list_by_category("file")
        assert len(file_tools) > 0
        for tool in file_tools:
            assert tool.category == "file"


class TestToolExecution:
    """工具执行测试"""
    
    @pytest.mark.asyncio
    async def test_read_file_tool(self):
        """测试读取文件工具"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("测试内容\n第二行")
            temp_path = f.name
        
        try:
            result = await tool_registry.execute("read_file", {"path": temp_path})
            assert result["success"] == True
            assert "测试内容" in result["result"]["content"]
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        result = await tool_registry.execute("read_file", {"path": "/nonexistent/file.txt"})
        assert result["success"] == True
        assert "error" in result["result"] or result["result"].get("content") is None
    
    @pytest.mark.asyncio
    async def test_write_file_tool(self):
        """测试写入文件工具"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_write.txt")
            result = await tool_registry.execute("write_file", {
                "path": file_path,
                "content": "测试写入内容"
            })
            assert result["success"] == True
            assert os.path.exists(file_path)
    
    @pytest.mark.asyncio
    async def test_list_directory_tool(self):
        """测试列出目录工具"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一些文件
            Path(tmpdir, "file1.txt").touch()
            Path(tmpdir, "file2.txt").touch()
            
            result = await tool_registry.execute("list_directory", {"path": tmpdir})
            assert result["success"] == True
            assert result["result"]["count"] == 2
    
    @pytest.mark.asyncio
    async def test_edit_file_tool(self):
        """测试编辑文件工具"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("原始内容")
            temp_path = f.name
        
        try:
            result = await tool_registry.execute("edit_file", {
                "path": temp_path,
                "old_text": "原始",
                "new_text": "修改后"
            })
            assert result["success"] == True
            
            # 验证修改
            with open(temp_path) as f:
                content = f.read()
            assert "修改后内容" in content
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_exec_command_tool_simple(self):
        """测试执行简单命令"""
        result = await tool_registry.execute("exec_command", {"command": "echo hello"})
        assert result["success"] == True
        assert "hello" in result["result"]["output"]
    
    @pytest.mark.asyncio
    async def test_exec_command_dangerous_blocked(self):
        """测试危险命令被阻止"""
        result = await tool_registry.execute("exec_command", {"command": "rm -rf /"})
        # 危险命令应该被阻止
        assert result["success"] == False or "error" in result["result"]


class TestToolDefinition:
    """工具定义测试"""
    
    def test_create_tool_definition(self):
        """测试创建工具定义"""
        def dummy_handler(arg1: str) -> dict:
            return {"result": arg1}
        
        tool = ToolDefinition(
            name="test_tool",
            description="测试工具",
            parameters={"type": "object", "properties": {}},
            handler=dummy_handler
        )
        
        assert tool.name == "test_tool"
        assert tool.description == "测试工具"
        assert tool.category == "general"
        assert tool.requires_auth == False
        assert tool.dangerous == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])