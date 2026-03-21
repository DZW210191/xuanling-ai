"""
文件操作技能 - 展示 Skills 系统功能
"""
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

# 导入技能基类
from skills import SkillBase, SkillMetadata, SkillConfig, SkillDependency, skill_action

logger = logging.getLogger("玄灵AI.Skills.FileOps")


class FileOpsSkill(SkillBase):
    """文件操作技能"""
    
    metadata = SkillMetadata(
        name="file_ops",
        version="1.0.0",
        description="文件操作技能 - 读写、搜索、管理文件",
        author="玄灵AI",
        category="file",
        tags=["file", "io", "filesystem"],
        dependencies=[
            SkillDependency(name="python:os", optional=False),
            SkillDependency(name="python:pathlib", optional=False),
        ],
        requires_auth=False,
        dangerous=True,
        config=SkillConfig(enabled=True, priority=50)
    )
    
    async def on_load(self):
        """加载时初始化"""
        self.register_handler("read", self.read_file)
        self.register_handler("write", self.write_file)
        self.register_handler("list", self.list_files)
        self.register_handler("search", self.search_files)
        self.register_handler("delete", self.delete_file)
        self.register_handler("mkdir", self.make_dir)
        
        logger.info("文件操作技能加载完成")
    
    async def on_unload(self):
        """卸载时清理"""
        logger.info("文件操作技能已卸载")
    
    async def read_file(self, params: Dict) -> Dict[str, Any]:
        """读取文件内容"""
        path = params.get("path")
        encoding = params.get("encoding", "utf-8")
        
        if not path:
            return {"success": False, "error": "缺少 path 参数"}
        
        try:
            file_path = Path(path)
            
            if not file_path.exists():
                return {"success": False, "error": f"文件不存在: {path}"}
            
            if not file_path.is_file():
                return {"success": False, "error": f"不是文件: {path}"}
            
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            return {
                "success": True,
                "path": str(file_path),
                "content": content,
                "size": len(content),
                "lines": content.count('\n') + 1
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def write_file(self, params: Dict) -> Dict[str, Any]:
        """写入文件"""
        path = params.get("path")
        content = params.get("content", "")
        mode = params.get("mode", "write")
        
        if not path:
            return {"success": False, "error": "缺少 path 参数"}
        
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            write_mode = 'a' if mode == "append" else 'w'
            with open(file_path, write_mode, encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "path": str(file_path),
                "mode": mode,
                "size": len(content)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def list_files(self, params: Dict) -> Dict[str, Any]:
        """列出文件"""
        path = params.get("path", ".")
        pattern = params.get("pattern", "*")
        
        try:
            dir_path = Path(path)
            
            if not dir_path.exists():
                return {"success": False, "error": f"目录不存在: {path}"}
            
            items = []
            for item in sorted(dir_path.glob(pattern)):
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            return {
                "success": True,
                "path": str(dir_path),
                "items": items,
                "count": len(items)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def search_files(self, params: Dict) -> Dict[str, Any]:
        """在文件中搜索"""
        path = params.get("path", ".")
        keyword = params.get("keyword")
        file_pattern = params.get("file_pattern", "*")
        
        if not keyword:
            return {"success": False, "error": "缺少 keyword 参数"}
        
        try:
            dir_path = Path(path)
            results = []
            
            for file_path in dir_path.rglob(file_pattern):
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line_num, line in enumerate(f, 1):
                                if keyword.lower() in line.lower():
                                    results.append({
                                        "file": str(file_path),
                                        "line": line_num,
                                        "content": line.strip()[:100]
                                    })
                                    if len(results) >= 100:
                                        break
                    except:
                        pass
            
            return {
                "success": True,
                "keyword": keyword,
                "results": results,
                "count": len(results)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def delete_file(self, params: Dict) -> Dict[str, Any]:
        """删除文件"""
        path = params.get("path")
        
        if not path:
            return {"success": False, "error": "缺少 path 参数"}
        
        try:
            file_path = Path(path).resolve()  # 解析真实路径
            
            if not file_path.exists():
                return {"success": False, "error": f"文件不存在: {path}"}
            
            # 安全检查：禁止删除系统目录
            dangerous_paths = ['/', '/etc', '/usr', '/var', '/home', '/root', '/boot', '/proc', '/sys']
            file_str = str(file_path)
            for dp in dangerous_paths:
                if file_str == dp or file_str.startswith(dp + '/'):
                    # 允许删除 /home/user/workspace 等用户工作目录
                    if dp in ['/home', '/root'] and len(file_str.split('/')) > 3:
                        continue
                    return {"success": False, "error": f"禁止删除系统目录: {dp}"}
            
            if file_path.is_file():
                file_path.unlink()
            else:
                import shutil
                shutil.rmtree(file_path)
            
            return {"success": True, "deleted": str(file_path)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def make_dir(self, params: Dict) -> Dict[str, Any]:
        """创建目录"""
        path = params.get("path")
        
        if not path:
            return {"success": False, "error": "缺少 path 参数"}
        
        try:
            dir_path = Path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            
            return {
                "success": True,
                "path": str(dir_path),
                "created": dir_path.exists()
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# 技能导出
skill_class = FileOpsSkill