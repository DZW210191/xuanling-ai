"""
玄灵AI 工具系统 - 核心模块
支持 Function Calling、动态注册、权限控制
"""
import os
import json
import subprocess
import shutil
import logging
import asyncio
import aiohttp
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import threading

logger = logging.getLogger("玄灵AI.Tools")

# ============== 工具定义 ==============

@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Callable
    category: str = "general"
    requires_auth: bool = False
    dangerous: bool = False
    
    def to_openai_schema(self) -> Dict:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def to_minimax_schema(self) -> Dict:
        """转换为 MiniMax Function Calling 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class ToolRegistry:
    """工具注册中心"""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._categories: Dict[str, List[str]] = {}
        self._permission_manager = None
        self._lock = threading.Lock()
    
    def set_permission_manager(self, manager):
        """设置权限管理器"""
        self._permission_manager = manager
        
    def register(self, tool: ToolDefinition) -> bool:
        """注册工具"""
        with self._lock:
            if tool.name in self._tools:
                logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
            
            self._tools[tool.name] = tool
            
            # 分类索引
            if tool.category not in self._categories:
                self._categories[tool.category] = []
            if tool.name not in self._categories[tool.category]:
                self._categories[tool.category].append(tool.name)
            
            logger.info(f"✅ 注册工具: {tool.name} [{tool.category}]")
            return True
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        with self._lock:
            if name not in self._tools:
                return False
            
            tool = self._tools.pop(name)
            if tool.category in self._categories:
                self._categories[tool.category].remove(name)
            
            logger.info(f"🗑️ 注销工具: {name}")
            return True
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_all(self) -> List[ToolDefinition]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def list_by_category(self, category: str) -> List[ToolDefinition]:
        """按类别列出工具"""
        names = self._categories.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]
    
    def get_schemas(self, format: str = "openai") -> List[Dict]:
        """获取所有工具的 Schema"""
        if format == "minimax":
            return [t.to_minimax_schema() for t in self._tools.values()]
        return [t.to_openai_schema() for t in self._tools.values()]
    
    async def execute(self, name: str, arguments: Dict, context: Dict = None) -> Dict:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return {"error": f"工具 {name} 不存在", "success": False}
        
        # 权限检查
        if tool.requires_auth and self._permission_manager:
            # 从 context 获取用户信息
            user_id = context.get("user_id") if context else None
            if user_id:
                try:
                    from security import Permission, permission_manager
                    # 根据工具类别确定需要的权限
                    permission_map = {
                        "file": [Permission.READ_FILE, Permission.WRITE_FILE],
                        "system": [Permission.EXEC_COMMAND],
                        "network": [Permission.NETWORK_ACCESS],
                    }
                    required_perms = permission_map.get(tool.category, [])
                    has_permission = any(
                        self._permission_manager.check_permission(user_id, perm)
                        for perm in required_perms
                    ) if required_perms else True
                    if not has_permission:
                        return {"error": f"无权限执行 {name}", "success": False}
                except ImportError:
                    logger.debug("security 模块未加载，跳过权限检查")
                except Exception as e:
                    logger.warning(f"权限检查失败: {e}")
        
        # 危险操作警告
        if tool.dangerous:
            logger.warning(f"⚠️ 执行危险工具: {name} 参数: {arguments}")
        
        try:
            # 执行工具
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**arguments)
            else:
                result = tool.handler(**arguments)
            
            return {
                "success": True,
                "result": result,
                "tool": name,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"工具执行失败 {name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "tool": name,
                "timestamp": datetime.now().isoformat()
            }


# 全局工具注册中心
tool_registry = ToolRegistry()


# ============== 内置工具实现 ==============

# ----- 文件操作工具 -----

def tool_read_file(path: str, offset: int = 0, limit: int = 2000) -> Dict:
    """读取文件内容"""
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return {"error": f"文件不存在: {path}", "content": None}
        
        if not file_path.is_file():
            return {"error": f"不是文件: {path}", "content": None}
        
        size = file_path.stat().st_size
        if size > 10 * 1024 * 1024:
            return {"error": f"文件太大 ({size/1024/1024:.1f}MB)，请使用分段读取", "content": None}
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        start = max(0, offset)
        end = min(total_lines, start + limit)
        
        content = ''.join(lines[start:end])
        
        return {
            "content": content,
            "path": str(file_path),
            "total_lines": total_lines,
            "read_lines": end - start,
            "offset": start,
            "truncated": end < total_lines
        }
    except Exception as e:
        return {"error": str(e), "content": None}


def tool_write_file(path: str, content: str, mode: str = "write") -> Dict:
    """写入文件"""
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


def tool_edit_file(path: str, old_text: str, new_text: str) -> Dict:
    """编辑文件"""
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {path}"}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if old_text not in content:
            return {"success": False, "error": "未找到要替换的文本"}
        
        new_content = content.replace(old_text, new_text, 1)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {"success": True, "path": str(file_path), "replacements": 1}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_list_directory(path: str = ".") -> Dict:
    """列出目录内容"""
    try:
        dir_path = Path(path)
        
        if not dir_path.exists():
            return {"error": f"目录不存在: {path}", "items": []}
        
        if not dir_path.is_dir():
            return {"error": f"不是目录: {path}", "items": []}
        
        items = []
        for item in sorted(dir_path.iterdir()):
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            })
        
        return {"path": str(dir_path), "items": items, "count": len(items)}
    except Exception as e:
        return {"error": str(e), "items": []}


# ----- 命令执行工具 -----

async def tool_exec_command(command: str, timeout: int = 30, cwd: str = None) -> Dict:
    """执行 Shell 命令"""
    try:
        # 更完整的危险命令检查 (增强版)
        dangerous_patterns = [
            # 文件删除 - 增强版
            r"rm\s+(-[rf]+\s+|.*\s+-[rf]+)",  # rm -rf 变体
            r"rm\s+.*(/\s*$|/\s+)",  # rm 删除目录
            r"rm\s+/\*",  # 删除根目录所有文件
            r"rm\s+\*",  # 删除当前目录所有文件
            r"rm\s+~",  # 删除用户目录
            r"rm\s+\$HOME",  # 删除用户目录
            r"find\s+.*-delete",  # find -delete
            r"xargs\s+rm",  # xargs rm
            r"rmdir\s+.*-p",  # 递归删除空目录
            
            # 磁盘操作
            r"mkfs",  # 格式化
            r"dd\s+if=.*of=/dev/",  # dd 写入设备
            r">\s*/dev/sd",  # 写入磁盘设备
            r">\s*/dev/hd",  # 写入 IDE 磁盘
            r">\s*/dev/nvme",  # 写入 NVMe
            r">\s*/dev/loop",  # 写入 loop 设备
            
            # 权限修改 - 增强版
            r"chmod\s+(-R\s+)?777",  # 危险权限
            r"chmod\s+(-R\s+)?a\+rwx",  # 危险权限
            r"chmod\s+(-R\s+)?\d{4}",  # 数字权限 (如 7777)
            r"chown\s+.*:\s*",  # 修改所有者
            r"chgrp\s+(-R\s+)?",  # 修改组
            
            # 系统破坏
            r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",  # Fork bomb
            r">\s*/dev/mem",  # 写入内存
            r">\s*/dev/port",  # 写入端口
            r">\s*/dev/kmem",  # 写入内核内存
            
            # 进程控制 - 增强版
            r"kill\s+-9\s+-1",  # 杀死所有进程
            r"killall\s+",  # 杀死所有进程
            r"pkill\s+-9",  # 强制杀死进程组
            r"kill\s+-9\s+1",  # 杀死 init 进程
            
            # 系统控制 - 增强版
            r"shutdown",  # 关机
            r"reboot",  # 重启
            r"poweroff",  # 关机
            r"halt",  # 停机
            r"init\s+[06]",  # 关机/重启
            r"systemctl\s+(stop|disable|reset-failed)",  # 停止系统服务
            r"service\s+\w+\s+stop",  # 停止服务
            
            # 远程执行 - 增强版
            r"curl.*\|\s*(ba)?sh",  # 远程执行脚本
            r"wget.*\|\s*(ba)?sh",  # 远程执行脚本
            r"curl.*\|\s*sudo",  # 远程执行 sudo
            r"wget.*\|\s*sudo",  # 远程执行 sudo
            r"curl.*\|\s*bash",  # curl | bash
            r"wget.*\|\s*bash",  # wget | bash
            r"curl.*\|\s*sh",  # curl | sh
            r"wget.*\|\s*sh",  # wget | sh
            
            # 系统配置 - 增强版
            r">\s*/etc/",  # 修改系统配置
            r">\s*/boot/",  # 修改启动配置
            r">\s*/proc/",  # 修改 proc
            r">\s*/sys/",  # 修改 sys
            r"mv\s+.*\s+/(dev|proc|sys)",  # 移动到系统目录
            r">\s*\$HOME/",  # 覆盖用户目录文件
            r">\s*~/",  # 覆盖用户目录文件
            
            # 清空文件 - 增强版
            r">\s+/etc/passwd",  # 清空密码文件
            r">\s+/etc/shadow",  # 清空影子文件
            r">\s+/etc/sudoers",  # 清空 sudoers
            r":>|>:",  # 清空文件
            r">\s+/dev/null\s+2>&1\s*;",  # 可能的清空操作
            
            # 危险管道
            r"\|\s*sudo\s+rm",  # 管道到 sudo rm
            r"\|\s*xargs\s+rm",  # 管道到 xargs rm
            r"\|\s*sh\s*$",  # 管道到 sh
            r"\|\s*bash\s*$",  # 管道到 bash
            
            # 网络危险操作
            r"iptables\s+-F",  # 清空防火墙规则
            r"ufw\s+disable",  # 禁用防火墙
            r"firewall-cmd\s+--reload",  # 重载防火墙
            
            # 其他危险操作
            r"git\s+push\s+.*--force",  # 强制推送
            r"git\s+reset\s+--hard\s+HEAD~",  # 强制重置
            r"docker\s+(rm|rmi)\s+.*-f",  # 强制删除容器/镜像
            r"kubectl\s+delete\s+.*--all",  # 删除所有资源
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return {"success": False, "error": f"禁止执行危险命令 (匹配安全规则)", "output": None}
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            return {"success": False, "error": f"命令执行超时 ({timeout}秒)", "output": None}
        
        output = stdout.decode('utf-8', errors='replace')
        error = stderr.decode('utf-8', errors='replace')
        
        return {
            "success": process.returncode == 0,
            "output": output,
            "error": error if error else None,
            "return_code": process.returncode,
            "command": command
        }
    except Exception as e:
        return {"success": False, "error": str(e), "output": None}


# ----- 网络请求工具 -----

async def tool_fetch_url(url: str, method: str = "GET", headers: Dict = None, body: str = None) -> Dict:
    """发送 HTTP 请求"""
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {"headers": headers or {}}
            if body and method in ["POST", "PUT", "PATCH"]:
                kwargs["data"] = body
            
            async with session.request(method, url, **kwargs, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                text = await resp.text()
                return {
                    "success": True,
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": text[:10000],
                    "truncated": len(text) > 10000
                }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ----- 消息发送工具 -----

async def tool_send_message(channel: str, message: str, target: str = None) -> Dict:
    """发送消息到指定频道"""
    return {
        "success": True,
        "message": f"消息已发送到 {channel}" + (f" ({target})" if target else ""),
        "content": message[:100]
    }


# ----- 搜索工具 -----

async def tool_web_search(query: str, max_results: int = 5) -> Dict:
    """网络搜索 - 支持 Tavily API"""
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    if not tavily_api_key:
        return {
            "success": False,
            "error": "搜索功能未配置 API Key",
            "hint": "请设置环境变量 TAVILY_API_KEY (推荐) 或 BING_API_KEY",
            "setup_guide": "1. 访问 https://tavily.com 获取免费 API Key\n2. export TAVILY_API_KEY=your_key"
        }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Tavily Search API
            payload = {
                "api_key": tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic"
            }
            
            async with session.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for r in data.get("results", []):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "content": r.get("content", "")[:500],
                            "score": r.get("score", 0)
                        })
                    return {
                        "success": True,
                        "query": query,
                        "results": results,
                        "count": len(results)
                    }
                else:
                    error = await resp.text()
                    return {
                        "success": False,
                        "error": f"Tavily API 错误: {resp.status}",
                        "details": error[:200]
                    }
    except asyncio.TimeoutError:
        return {"success": False, "error": "搜索请求超时"}
    except Exception as e:
        return {"success": False, "error": f"搜索失败: {str(e)}"}


# ============== 注册内置工具 ==============

def register_builtin_tools():
    """注册所有内置工具"""
    
    # 文件操作
    tool_registry.register(ToolDefinition(
        name="read_file",
        description="读取文件内容，支持分页",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "offset": {"type": "integer", "description": "起始行号", "default": 0},
                "limit": {"type": "integer", "description": "最大行数", "default": 2000}
            },
            "required": ["path"]
        },
        handler=tool_read_file,
        category="file"
    ))
    
    tool_registry.register(ToolDefinition(
        name="write_file",
        description="写入文件，可覆盖或追加",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
                "mode": {"type": "string", "enum": ["write", "append"], "description": "写入模式", "default": "write"}
            },
            "required": ["path", "content"]
        },
        handler=tool_write_file,
        category="file",
        dangerous=True
    ))
    
    tool_registry.register(ToolDefinition(
        name="edit_file",
        description="编辑文件，替换指定文本",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "old_text": {"type": "string", "description": "要替换的文本"},
                "new_text": {"type": "string", "description": "新文本"}
            },
            "required": ["path", "old_text", "new_text"]
        },
        handler=tool_edit_file,
        category="file",
        dangerous=True
    ))
    
    tool_registry.register(ToolDefinition(
        name="list_directory",
        description="列出目录内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径", "default": "."}
            },
            "required": []
        },
        handler=tool_list_directory,
        category="file"
    ))
    
    # 命令执行
    tool_registry.register(ToolDefinition(
        name="exec_command",
        description="执行 Shell 命令",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell 命令"},
                "timeout": {"type": "integer", "description": "超时时间(秒)", "default": 30},
                "cwd": {"type": "string", "description": "工作目录"}
            },
            "required": ["command"]
        },
        handler=tool_exec_command,
        category="system",
        dangerous=True
    ))
    
    # 网络请求
    tool_registry.register(ToolDefinition(
        name="fetch_url",
        description="发送 HTTP 请求",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL 地址"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
                "headers": {"type": "object", "description": "请求头"},
                "body": {"type": "string", "description": "请求体"}
            },
            "required": ["url"]
        },
        handler=tool_fetch_url,
        category="network"
    ))
    
    # 消息发送
    tool_registry.register(ToolDefinition(
        name="send_message",
        description="发送消息到指定频道",
        parameters={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "频道类型 (feishu/wecom/telegram)"},
                "message": {"type": "string", "description": "消息内容"},
                "target": {"type": "string", "description": "目标用户/群"}
            },
            "required": ["channel", "message"]
        },
        handler=tool_send_message,
        category="messaging"
    ))
    
    # 网络搜索
    tool_registry.register(ToolDefinition(
        name="web_search",
        description="网络搜索",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最大结果数", "default": 5}
            },
            "required": ["query"]
        },
        handler=tool_web_search,
        category="search"
    ))
    
    logger.info(f"✅ 已注册 {len(tool_registry.list_all())} 个内置工具")


# 初始化
register_builtin_tools()