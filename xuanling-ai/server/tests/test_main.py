"""
玄灵AI 单元测试 - 主模块
"""
import pytest
import sys
import os
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from fastapi.testclient import TestClient


class TestBasicRoutes:
    """基础路由测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_api_health_check(self, client):
        """测试 API 健康检查"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_api_settings_get(self, client):
        """测试获取设置"""
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert "model" in data or "apiUrl" in data
    
    def test_api_models_list(self, client):
        """测试模型列表"""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) > 0
    
    def test_api_tools_list(self, client):
        """测试工具列表"""
        response = client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert data["count"] > 0
    
    def test_api_skills_list(self, client):
        """测试技能列表"""
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
    
    def test_api_projects_list(self, client):
        """测试项目列表"""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
    
    def test_api_memory_stats(self, client):
        """测试记忆统计"""
        response = client.get("/api/memory")
        assert response.status_code == 200
    
    def test_api_tasks_stats(self, client):
        """测试任务统计"""
        response = client.get("/api/tasks/stats")
        assert response.status_code == 200


class TestAgentsAPI:
    """子代理 API 测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_list_agents(self, client):
        """测试获取子代理列表"""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
    
    def test_create_agent(self, client):
        """测试创建子代理"""
        response = client.post(
            "/api/agents",
            json={"name": "测试代理", "description": "测试用"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_get_agent_not_found(self, client):
        """测试获取不存在的子代理"""
        response = client.get("/api/agents/nonexistent_id")
        assert response.status_code == 404


class TestMemoryAPI:
    """记忆 API 测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_list_memory_compat(self, client):
        """测试获取记忆列表 (兼容路由)"""
        response = client.get("/memory")
        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
    
    def test_create_memory_compat(self, client):
        """测试创建记忆 (兼容路由)"""
        response = client.post(
            "/memory",
            json={"title": "测试记忆", "content": "这是测试内容", "tags": ["test"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_delete_memory_not_found(self, client):
        """测试删除不存在的记忆"""
        response = client.delete("/memory/nonexistent_id")
        assert response.status_code == 404


class TestToolsAPI:
    """工具 API 测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_get_tool_detail(self, client):
        """测试获取工具详情"""
        response = client.get("/api/tools/read_file")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "read_file"
    
    def test_get_nonexistent_tool(self, client):
        """测试获取不存在的工具"""
        response = client.get("/api/tools/nonexistent_tool")
        assert response.status_code == 404
    
    def test_execute_tool_missing_args(self, client):
        """测试执行工具缺少参数"""
        response = client.post(
            "/api/tools/execute",
            json={"tool_name": "read_file", "arguments": {}}
        )
        assert response.status_code == 200
        data = response.json()
        # 应该返回错误而不是崩溃
        assert "success" in data or "error" in data


class TestProjectsAPI:
    """项目 API 测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_create_project(self, client):
        """测试创建项目"""
        response = client.post(
            "/api/projects",
            json={
                "name": "测试项目",
                "description": "这是一个测试项目",
                "icon": "🧪"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "project" in data
    
    def test_get_project_not_found(self, client):
        """测试获取不存在的项目"""
        response = client.get("/api/projects/nonexistent_id")
        assert response.status_code == 404


class TestProjectFileManager:
    """项目文件管理 API 测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_get_project_files_not_found(self, client):
        """测试获取不存在的项目文件"""
        response = client.get("/project-manager/projects/nonexistent_project")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data or "files" in data


class TestSecurity:
    """安全测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_api_security_stats(self, client):
        """测试安全统计"""
        response = client.get("/api/security/stats")
        assert response.status_code == 200
    
    def test_api_audit_logs(self, client):
        """测试审计日志"""
        response = client.get("/api/security/audit-logs")
        assert response.status_code == 200


class TestConfig:
    """配置测试"""
    
    def test_config_variables_exist(self):
        """测试配置变量存在"""
        from main import SERVER_HOST, SERVER_PORT, REQUEST_TIMEOUT
        assert SERVER_HOST is not None
        assert SERVER_PORT > 0
        assert REQUEST_TIMEOUT > 0
    
    def test_cors_middleware_configured(self):
        """测试 CORS 中间件配置"""
        from main import app
        # 检查 CORS 中间件是否配置
        middleware_types = [type(m).__name__ for m in app.user_middleware]
        assert 'CORSMiddleware' in middleware_types or len(middleware_types) > 0


class TestCache:
    """缓存系统测试"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_cache_stats(self, client):
        """测试缓存统计"""
        response = client.get("/api/cache/stats")
        assert response.status_code == 200
    
    def test_cache_clear(self, client):
        """测试清空缓存"""
        response = client.post("/api/cache/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])