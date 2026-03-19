"""
Core - 核心模块
"""
from typing import List, Dict, Any, Optional
import json
import time
import re


class Session:
    """会话"""
    
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = time.time()
        self.updated_at = time.time()
        self.context: Dict = {}
        self.history: List[Dict] = []
    
    def add_turn(self, user: str, assistant: str):
        """添加对话轮次"""
        self.history.append({
            "user": user,
            "assistant": assistant,
            "timestamp": time.time()
        })
        self.updated_at = time.time()
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取历史"""
        return self.history[-limit:]
    
    def set_context(self, key: str, value: Any):
        """设置上下文"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self.context.get(key, default)


class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self, session_id: str, user_id: str) -> Session:
        """创建会话"""
        session = Session(session_id, user_id)
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def get_or_create(self, session_id: str, user_id: str) -> Session:
        """获取或创建"""
        if session_id not in self.sessions:
            return self.create_session(session_id, user_id)
        return self.sessions[session_id]


class Agent:
    """AI 代理核心"""
    
    def __init__(self, model, memory, skills, config: Dict = None):
        self.name = config.get("name", "玄灵AI")
        self.model = model
        self.memory = memory
        self.skills = skills
        self.config = config or {}
        self.sessions = SessionManager()
        
        # 系统提示词
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        from src.tools import get_available_tools
        
        tools_list = get_available_tools()
        tools_desc = """
## 可用工具
当用户需要执行实际操作时，你可以使用以下工具：
- read <文件路径> - 读取文件内容
- write <文件路径> <内容> - 写入文件
- edit <文件路径> <旧内容> <新内容> - 精确编辑文件
- ls <目录路径> - 列出目录内容
- run <命令> - 执行系统命令
- fetch <URL> - 获取网页内容
- github <仓库URL> - 获取GitHub仓库信息
- browse <URL> - 浏览网页
- search <关键词> - 搜索信息
- sysinfo - 获取系统信息
- processes - 查看运行进程
- memory_search <关键词> - 搜索长期记忆
- skills - 列出可用技能
- weather <城市> - 查询天气

**重要**：当用户要求你完成实际任务时，请立即使用相应工具。
- 用户发来GitHub链接 → 使用 github 工具
- 用户发来网页URL → 使用 fetch 工具
- 用户要求截图 → 使用 browse 工具

不要只是描述如何做，要直接去做！"""
        
        return f"""你是 {self.name}，一个智能 AI 助手。

你的能力：
• 智能对话和问答
• 帮助用户完成各种实际任务
• 读取、写入文件
• 执行系统命令
• 获取网页信息
• 查看系统状态
• **记住对话上下文** - 你会记得用户之前说过的话

重要规则：
1. 如果用户要求你完成实际任务，立即使用工具执行
2. 执行后返回结果给用户
3. **必须记住用户之前告诉你的信息**（如名字、偏好等）
4. 不要每次都说"你没有告诉我"，要查看对话历史{tools_desc}

请用友好、专业的方式回复。"""
    
    async def handle(self, message) -> str:
        """处理消息"""
        # 分析消息，判断是否需要执行工具
        response = await self._handle_with_tools(message.content)
        
        # 检查是否需要保存到长期记忆
        # 如果用户明确要求"记住"或对话中包含重要信息
        content = message.content.lower()
        important_keywords = ['记住', '不要忘记', '重要', '记住这个', '记得', 'always', 'remember']
        
        if any(kw in content for kw in important_keywords):
            # 保存到长期记忆
            title = message.content[:30] + "..."
            await self.memory.add_memory(
                title=title,
                content=f"用户: {message.content}\n助手: {response}",
                tags=["对话记忆", "重要"]
            )
        
        return response
    
    async def _handle_with_tools(self, user_message: str) -> str:
        """带工具调用的处理"""
        from src.tools import execute_tool, get_available_tools
        
        # 构建系统消息，包含工具说明
        tools = get_available_tools()
        
        # 先判断用户意图
        need_tool = False
        tool_name = None
        tool_args = {}
        
        msg = user_message.lower()
        
        # 读取文件
        if any(k in msg for k in ['读文件', '查看文件', 'cat', 'read']):
            for word in user_message.split():
                if '/' in word or '.py' in word or '.yaml' in word or '.md' in word:
                    tool_name = 'read'
                    tool_args = {'path': word.strip()}
                    need_tool = True
                    break
        
        # 写入文件
        elif any(k in msg for k in ['写文件', '创建文件', 'write']):
            # 简单提取文件名和内容
            parts = user_message.split()
            if len(parts) >= 3:
                tool_name = 'write'
                tool_args = {'path': parts[1], 'content': ' '.join(parts[2:])}
                need_tool = True
        
        # 编辑文件
        elif any(k in msg for k in ['编辑', '修改', 'edit']):
            tool_name = 'edit'
            need_tool = True
        
        # 列出目录
        elif any(k in msg for k in ['列出', '目录', 'ls', 'list', '看看有什么']):
            path = '.'
            for word in user_message.split():
                if '/' in word:
                    path = word.strip()
                    break
            tool_name = 'ls'
            tool_args = {'path': path}
            need_tool = True
        
        # 执行命令
        elif any(k in msg for k in ['执行', '运行命令', 'run', '命令行']):
            # 从消息中提取命令
            if 'run' in user_message.lower():
                idx = user_message.lower().find('run')
                cmd = user_message[idx+3:].strip()
                if cmd:
                    tool_name = 'run'
                    tool_args = {'command': cmd}
                    need_tool = True
        
        # 系统信息
        elif any(k in msg for k in ['系统信息', 'sysinfo', '查看配置', '服务器状态']):
            tool_name = 'sysinfo'
            need_tool = True
        
        # 进程
        elif any(k in msg for k in ['进程', 'process', '运行中']):
            tool_name = 'processes'
            need_tool = True
        
        # 搜索记忆
        elif any(k in msg for k in ['搜索记忆', 'memory_search', '记得']):
            # 提取搜索词
            query = user_message.replace('搜索记忆', '').replace('记得', '').strip()
            tool_name = 'memory_search'
            tool_args = {'query': query}
            need_tool = True
        
        # 技能
        elif any(k in msg for k in ['技能', '有哪些能力', '能做什么']):
            tool_name = 'skills'
            need_tool = True
        
        # 天气
        elif any(k in msg for k in ['天气', '多少度', '温度']):
            # 提取城市
            city = "北京"
            for word in user_message:
                if '天气' not in word and len(word) >= 2:
                    city = word.strip()
            tool_name = 'weather'
            tool_args = {'city': city}
            need_tool = True
        
        # GitHub仓库
        elif 'github.com' in user_message:
            tool_name = 'github'
            tool_args = {'repo_url': user_message}
            need_tool = True
        
        # 自然语言打开网页 - 自动补全URL
        elif any(k in msg for k in ['打开', '访问', '去', '看看']):
            # 常见网站自动补全
            url = None
            if '百度' in user_message:
                url = 'https://www.baidu.com'
            elif '谷歌' in user_message or 'google' in user_message.lower():
                url = 'https://www.google.com'
            elif '淘宝' in user_message:
                url = 'https://www.taobao.com'
            elif '京东' in user_message:
                url = 'https://www.jd.com'
            elif '知乎' in user_message:
                url = 'https://www.zhihu.com'
            elif '微博' in user_message:
                url = 'https://www.weibo.com'
            elif 'B站' in user_message or 'bilibili' in user_message.lower():
                url = 'https://www.bilibili.com'
            elif 'GitHub' in user_message:
                url = 'https://github.com'
            elif 'youtube' in user_message.lower():
                url = 'https://www.youtube.com'
            
            if url:
                tool_name = 'fetch'
                tool_args = {'url': url}
                need_tool = True
            else:
                # 没有匹配到常见网站，返回提示
                return f"🌐 请提供要打开的网页地址，例如：打开百度、打开GitHub、打开淘宝 等"
        
        # 读取网页
        elif any(k in msg for k in ['读取', '打开', '访问', 'fetch', 'http']):
            # 检测URL
            import re
            urls = re.findall(r'https?://[^\s]+', user_message)
            if urls:
                tool_name = 'fetch'
                tool_args = {'url': urls[0]}
                need_tool = True
        
        # 浏览器/截图
        elif any(k in msg for k in ['截图', 'screenshot', '截屏', '浏览器']):
            import re
            urls = re.findall(r'https?://[^\s]+', user_message)
            if urls:
                tool_name = 'browse'
                tool_args = {'url': urls[0], 'action': 'screenshot'}
                need_tool = True
            else:
                return "🔍 请提供要截图的网页URL，例如: 截图 https://example.com"
        
        # 执行工具
        if need_tool and tool_name:
            try:
                result = await execute_tool(tool_name, **tool_args)
                # 保存到记忆
                self.memory.add_turn(user_message, f"[执行工具: {tool_name}]\n{result}")
                return f"✅ 已执行 {tool_name}:\n\n{result}"
            except Exception as e:
                return f"❌ 执行失败: {str(e)}"
        
        # 如果不需要工具，走正常对话流程
        history = self.memory.get_recent(5)
        
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 添加历史对话
        for h in history:
            messages.append({"role": "user", "content": h.get("content", "").split('\n')[0]})
            # 从content中提取助手回复
            content = h.get("content", "")
            if "助手:" in content:
                assistant_msg = content.split("助手:")[-1].strip()
                messages.append({"role": "assistant", "content": assistant_msg})
        
        messages.append({"role": "user", "content": user_message})
        
        response = await self.model.chat(messages)
        
        # 保存到记忆
        self.memory.add_turn(user_message, response)
        
        # 保存到记忆
        self.memory.add_turn(user_message, response)
        
        return response
    
    async def handle_with_context(self, message, context: Dict) -> str:
        """带上下文处理"""
        # 合并上下文到系统提示
        context_prompt = self.system_prompt
        if "project" in context:
            context_prompt += f"\n\n当前项目: {context['project']}"
        
        # 调用模型
        messages = [
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": message.content}
        ]
        
        response = await self.model.chat(messages)
        
        return response


class Config:
    """配置管理"""
    
    def __init__(self, config: Dict = None):
        self.data = config or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        keys = key.split(".")
        value = self.data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any):
        """设置配置"""
        keys = key.split(".")
        data = self.data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value
