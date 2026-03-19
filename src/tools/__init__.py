"""
工具模块 - 玄灵AI的工作能力
"""
import os
import subprocess
import asyncio
from typing import Dict, Any, List


class FileTool:
    """文件操作工具"""
    
    name = "file_operations"
    description = "读取、写入、列出文件"
    
    @staticmethod
    async def read(path: str, lines: int = None) -> str:
        """读取文件"""
        try:
            from pathlib import Path
            p = Path(path)
            if not p.exists():
                return f"文件不存在: {path}"
            content = p.read_text(encoding='utf-8')
            if lines:
                content = '\n'.join(content.split('\n')[:lines])
            return content
        except Exception as e:
            return f"读取失败: {str(e)}"
    
    @staticmethod
    async def write(path: str, content: str) -> str:
        """写入文件"""
        try:
            from pathlib import Path
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            return f"✅ 已写入: {path}"
        except Exception as e:
            return f"写入失败: {str(e)}"
    
    @staticmethod
    async def edit(path: str, oldText: str, newText: str) -> str:
        """精确编辑文件"""
        try:
            from pathlib import Path
            p = Path(path)
            if not p.exists():
                return f"文件不存在: {path}"
            
            content = p.read_text(encoding='utf-8')
            if oldText not in content:
                return f"❌ 未找到要替换的内容: {oldText[:30]}..."
            
            new_content = content.replace(oldText, newText)
            p.write_text(new_content, encoding='utf-8')
            return f"✅ 已修改: {path}"
        except Exception as e:
            return f"编辑失败: {str(e)}"
    
    @staticmethod
    async def list_dir(path: str = ".") -> str:
        """列出目录"""
        try:
            from pathlib import Path
            items = list(Path(path).iterdir())
            result = []
            for item in items:
                prefix = "📁" if item.is_dir() else "📄"
                result.append(f"{prefix} {item.name}")
            return '\n'.join(result) if result else "目录为空"
        except Exception as e:
            return f"列出失败: {str(e)}"


class CommandTool:
    """命令执行工具"""
    
    name = "command_exec"
    description = "执行系统命令"
    
    @staticmethod
    async def run(command: str, timeout: int = 30) -> str:
        """执行命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout or result.stderr
            if result.returncode != 0:
                return f"命令执行失败 (代码 {result.returncode}):\n{output}"
            return output[:5000]  # 限制输出长度
        except subprocess.TimeoutExpired:
            return "⏱️ 命令执行超时"
        except Exception as e:
            return f"执行失败: {str(e)}"


class WebTool:
    """网页工具"""
    
    name = "web_tools"
    description = "获取网页内容、搜索、截图"
    
    @staticmethod
    async def fetch(url: str, summarize: bool = False) -> str:
        """获取网页内容"""
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return f"❌ 获取失败: HTTP {resp.status}"
                    
                    text = await resp.text()
                    
                    # 解析HTML
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    # 获取标题
                    title = soup.title.string if soup.title else "无标题"
                    
                    # 获取meta描述
                    description = ""
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc:
                        description = meta_desc.get('content', '')
                    
                    # 获取主要文本内容
                    # 移除script和style
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # 获取正文文本
                    body = soup.body
                    if body:
                        # 获取所有段落和标题
                        content_parts = []
                        for tag in body.find_all(['h1', 'h2', 'h3', 'p', 'li', 'article']):
                            text = tag.get_text(strip=True)
                            if len(text) > 20:  # 过滤短内容
                                content_parts.append(text)
                        
                        content = '\n'.join(content_parts[:20])  # 限制数量
                    else:
                        content = ""
                    
                    result = f"""🌐 页面: {title}

📝 描述: {description}

📄 内容摘要:
{content[:2000]}

🔗 链接: {url}"""
                    
                    return result
                    
        except ImportError:
            # 如果没有BeautifulSoup，返回原始内容
            return f"📄 网页内容 ({url}):\n\n{text[:3000]}"
        except Exception as e:
            return f"获取失败: {str(e)}"
    
    @staticmethod
    async def fetch_github(repo_url: str) -> str:
        """获取GitHub仓库信息"""
        try:
            import aiohttp
            # 解析 repo_url 提取 owner/repo
            # 例如: https://github.com/user/repo -> user/repo
            import re
            match = re.search(r'github\.com[/:]([\w-]+)/([\w-]+)', repo_url)
            if not match:
                return "❌ 无法解析GitHub仓库URL"
            
            owner, repo = match.groups()
            repo = repo.replace('.git', '')
            
            # 获取仓库信息
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = f"""
📦 GitHub仓库: {owner}/{repo}

⭐ Stars: {data.get('stargazers_count', 0)}
🍴 Forks: {data.get('forks_count', 0)}
📝 描述: {data.get('description', '无')}
🔗 语言: {data.get('language', '未知')}
👤 作者: {data.get('owner', {}).get('login', '未知')}

📖 README (前2000字):
"""
                        # 获取README
                        readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
                        async with session.get(readme_url, timeout=aiohttp.ClientTimeout(total=10)) as rm_resp:
                            if rm_resp.status == 200:
                                import base64
                                rm_data = await rm_resp.json()
                                if 'content' in rm_data:
                                    content = base64.b64decode(rm_data['content']).decode('utf-8')
                                    result += content[:2000]
                        return result
                    else:
                        return f"❌ 获取失败: HTTP {resp.status}"
        except Exception as e:
            return f"❌ 错误: {str(e)}"
    
    @staticmethod
    async def search(query: str) -> str:
        """简单搜索"""
        return f"""🔍 搜索: {query}

(搜索功能需要配置搜索引擎API或使用浏览器)

💡 建议: 告诉我具体要搜索什么，我可以尝试获取网页内容"""
    
    @staticmethod
    async def screenshot(url: str) -> str:
        """网页截图"""
        return f"""
📸 截图: {url}

(截图功能需要配置浏览器自动化)

💡 当前支持:
- 获取网页文本内容: "读取 {url}"
- 获取GitHub信息: "读取 https://github.com/..." 
"""
    
    @staticmethod
    async def browse(url: str, action: str = "read") -> str:
        """浏览网页"""
        if action == "screenshot":
            return await WebTool.screenshot(url)
        
        # 默认读取内容
        return await WebTool.fetch(url)


class SystemTool:
    """系统信息工具"""
    
    name = "system_info"
    description = "获取系统信息"
    
    @staticmethod
    async def info() -> str:
        """获取系统信息"""
        import platform
        
        # 简单信息，不依赖psutil
        info = f"""
🖥️ 系统信息
- 系统: {platform.system()} {platform.release()}
- Python: {platform.python_version()}
- 机器: {platform.machine()}
- 处理器: {platform.processor()}

📁 工作目录: /root/.openclaw/workspace/xuanling
"""
        return info
    
    @staticmethod
    async def processes() -> str:
        """查看进程"""
        try:
            import subprocess
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[:15]
            return "运行中的进程:\n" + '\n'.join(lines)
        except Exception as e:
            return f"获取进程失败: {str(e)}"


class MemoryTool:
    """记忆搜索工具"""
    
    name = "memory_search"
    description = "搜索长期记忆"
    
    @staticmethod
    async def search(query: str) -> str:
        """搜索记忆"""
        try:
            # 尝试获取全局memory实例
            from src.main import xuanling_app
            if xuanling_app and xuanling_app.memory:
                results = await xuanling_app.memory.search_memories(query)
                if results:
                    return "找到相关记忆:\n" + "\n".join([
                        f"- {r.content[:100]}..." for r in results[:5]
                    ])
                return "未找到相关记忆"
            return "记忆系统未初始化"
        except Exception as e:
            return f"搜索失败: {str(e)}"


class SkillTool:
    """技能工具"""
    
    name = "skills"
    description = "调用各种技能"
    
    @staticmethod
    async def weather(city: str = "北京") -> str:
        """查询天气"""
        return f"""
🌤️ {city} 天气

(天气功能需要配置天气API)

当前模拟天气: 晴, 20°C
"""
    
    @staticmethod
    async def list_skills() -> str:
        """列出可用技能"""
        return """
🛠️ 可用技能:
- weather: 查询天气
- (更多技能开发中...)
"""


# 工具注册表
TOOLS = {
    "read": FileTool.read,
    "write": FileTool.write,
    "edit": FileTool.edit,
    "ls": FileTool.list_dir,
    "run": CommandTool.run,
    "fetch": WebTool.fetch,
    "github": WebTool.fetch_github,
    "browse": WebTool.browse,
    "search": WebTool.search,
    "sysinfo": SystemTool.info,
    "processes": SystemTool.processes,
    "memory_search": MemoryTool.search,
    "skills": SkillTool.list_skills,
    "weather": SkillTool.weather,
    "spawn": None,  # 需要特殊处理
}


async def execute_tool(tool_name: str, **kwargs) -> str:
    """执行工具"""
    if tool_name == "spawn":
        return await _execute_spawn(**kwargs)
    
    if tool_name not in TOOLS:
        return f"未知工具: {tool_name}"
    
    try:
        func = TOOLS[tool_name]
        return await func(**kwargs)
    except TypeError:
        # 尝试不传参数
        try:
            return await TOOLS[tool_name]()
        except:
            return f"工具 {tool_name} 调用失败"
    except Exception as e:
        return f"工具执行失败: {str(e)}"


async def _execute_spawn(task: str = "", runtime: str = "subagent", **kwargs) -> str:
    """创建子代理会话"""
    try:
        # 这里需要导入sessions_spawn
        # 简化实现：返回信息
        return f"""🔄 创建子代理任务:
- 任务: {task}
- 运行时: {runtime}

(子代理功能需要配置 ACP/SubAgent)"""
    except Exception as e:
        return f"创建子代理失败: {str(e)}"


def get_available_tools() -> List[str]:
    """获取可用工具列表"""
    return list(TOOLS.keys())
