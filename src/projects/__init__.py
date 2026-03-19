"""
项目管理器 - 创建项目文件夹结构
"""
import os
import json
from pathlib import Path
from datetime import datetime


class ProjectManager:
    """项目管理器"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or "/root/.openclaw/workspace/xuanling/projects")
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def create_project(self, name: str, description: str = "") -> dict:
        """创建项目及文件夹结构"""
        project_path = self.base_path / name
        project_path.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        folders = {
            "docs": "项目文档",
            "memory": "项目记忆",
            "knowledge": "知识库",
            "code": "代码文件",
            "data": "开发数据",
            "configs": "配置文件",
            "logs": "日志文件",
            "assets": "资源文件"
        }
        
        created = []
        for folder, desc in folders.items():
            folder_path = project_path / folder
            folder_path.mkdir(parents=True, exist_ok=True)
            created.append({"folder": folder, "desc": desc})
        
        # 创建项目配置文件
        project_info = {
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "folders": created
        }
        
        with open(project_path / ".project.json", "w", encoding="utf-8") as f:
            json.dump(project_info, f, ensure_ascii=False, indent=2)
        
        return {"status": "ok", "project": name, "path": str(project_path), "folders": created}
    
    def list_projects(self) -> list:
        """列出所有项目"""
        projects = []
        for p in self.base_path.iterdir():
            if p.is_dir():
                info_file = p / ".project.json"
                if info_file.exists():
                    with open(info_file, "r", encoding="utf-8") as f:
                        info = json.load(f)
                        projects.append(info)
                else:
                    projects.append({"name": p.name, "description": ""})
        return projects
    
    def get_project(self, name: str) -> dict:
        """获取项目详情"""
        project_path = self.base_path / name
        if not project_path.exists():
            return {"error": "项目不存在"}
        
        # 读取项目信息
        info_file = project_path / ".project.json"
        info = {}
        if info_file.exists():
            with open(info_file, "r", encoding="utf-8") as f:
                info = json.load(f)
        
        # 列出所有文件
        files = []
        for f in project_path.rglob("*"):
            if f.is_file():
                rel_path = f.relative_to(project_path)
                files.append({
                    "path": str(rel_path),
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
        
        return {"project": info, "files": files}
    
    def add_memory(self, project: str, title: str, content: str, tags: list = None) -> dict:
        """添加项目记忆"""
        project_path = self.base_path / project / "memory"
        project_path.mkdir(parents=True, exist_ok=True)
        
        # 创建记忆文件
        memory_file = project_path / f"{title}.md"
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**创建时间**: {datetime.now().isoformat()}\n\n")
            if tags:
                f.write(f"**标签**: {', '.join(tags)}\n\n")
            f.write(f"---\n\n")
            f.write(content)
        
        return {"status": "ok", "file": str(memory_file)}
    
    def add_doc(self, project: str, title: str, content: str) -> dict:
        """添加项目文档"""
        project_path = self.base_path / project / "docs"
        project_path.mkdir(parents=True, exist_ok=True)
        
        doc_file = project_path / f"{title}.md"
        with open(doc_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {"status": "ok", "file": str(doc_file)}
    
    def read_file(self, project: str, file_path: str) -> str:
        """读取项目文件"""
        full_path = self.base_path / project / file_path
        if not full_path.exists():
            return f"文件不存在: {file_path}"
        
        try:
            return full_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取失败: {str(e)}"
    
    def delete_project(self, name: str) -> dict:
        """删除项目"""
        import shutil
        project_path = self.base_path / name
        if not project_path.exists():
            return {"error": "项目不存在"}
        
        shutil.rmtree(project_path)
        return {"status": "ok", "message": f"项目 {name} 已删除"}


# 全局实例
project_manager = ProjectManager()
