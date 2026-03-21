"""
玄灵AI 引擎 - 支持工具调用的 AI 对话引擎
"""
import os
import re
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime

# 导入工具系统
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import tool_registry

logger = logging.getLogger("玄灵AI.Engine")

# ============== 配置 ==============

DEFAULT_SYSTEM_PROMPT = """你是玄灵AI，一个智能助手。你可以使用工具来帮助用户完成任务。

## 你的能力
- 文件操作：读取、写入、编辑文件
- 命令执行：运行 Shell 命令
- 网络请求：发送 HTTP 请求
- 消息发送：发送消息到各平台
- 网络搜索：搜索网络信息

## 工作方式
1. 理解用户需求
2. 选择合适的工具
3. 执行操作并返回结果
4. 用自然语言解释你的操作

请始终使用中文回复。"""


# ============== AI 引擎 ==============

class AIEngine:
    """AI 对话引擎 - 支持 Function Calling"""
    
    def __init__(self):
        self.api_key = os.getenv("MINIMAX_API_KEY", "")
        self.api_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
        self.model = "MiniMax-M2.5"
        self.max_tool_calls = 5  # 最大工具调用轮数
        self.max_history = 100  # 最大历史记录数
        self.conversation_history: List[Dict] = []
        
    def _trim_history(self):
        """限制历史记录长度"""
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        
    def configure(self, api_key: str = None, api_url: str = None, model: str = None):
        """配置引擎"""
        if api_key:
            self.api_key = api_key
        if api_url:
            self.api_url = api_url
        if model:
            self.model = model
        logger.info(f"引擎配置: model={self.model}, url={self.api_url}")
    
    def _get_tools_schema(self, format: str = "openai") -> List[Dict]:
        """获取工具定义"""
        return tool_registry.get_schemas(format)
    
    async def _call_llm(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """调用 LLM API"""
        if not self.api_key or self.api_key == "test-key":
            # 无 API Key，使用模拟模式
            return await self._mock_llm_call(messages, tools)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        # 添加工具定义
        if tools:
            payload["tools"] = tools
        
        # MiniMax API 端点
        if "minimax" in self.api_url.lower():
            endpoint = f"{self.api_url}/text/chatcompletion_v2"
        else:
            # OpenAI 兼容格式
            endpoint = f"{self.api_url}/chat/completions"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self._parse_response(data)
                    else:
                        error = await resp.text()
                        logger.error(f"LLM API 错误: {resp.status} - {error}")
                        return {
                            "type": "error",
                            "content": f"API 错误: {resp.status}",
                            "error": error[:200]
                        }
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return {"type": "error", "content": str(e), "error": str(e)}
    
    def _parse_response(self, data: Dict) -> Dict:
        """解析 API 响应"""
        # OpenAI 格式
        if "choices" in data:
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            # 检查是否有工具调用
            if "tool_calls" in message and message["tool_calls"]:
                return {
                    "type": "tool_calls",
                    "tool_calls": message["tool_calls"],
                    "content": message.get("content", "")
                }
            
            return {
                "type": "text",
                "content": message.get("content", "")
            }
        
        # MiniMax 格式
        if "base_resp" in data:
            if data["base_resp"].get("status_code") != 0:
                return {
                    "type": "error",
                    "content": data["base_resp"].get("status_msg", "未知错误"),
                    "error": data["base_resp"].get("status_msg")
                }
        
        # 尝试提取内容
        if "choices" in data:
            return {"type": "text", "content": data["choices"][0].get("message", {}).get("content", "")}
        
        return {"type": "text", "content": str(data)}
    
    async def _mock_llm_call(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """模拟 LLM 调用（无 API Key 时）"""
        last_message = messages[-1]["content"].lower() if messages else ""
        
        # 模拟工具调用
        if "读取" in last_message or "查看" in last_message:
            if "文件" in last_message or any(ext in last_message for ext in [".txt", ".py", ".md", ".json"]):
                # 提取文件路径
                path_match = re.search(r'[\'"]?(/[^\s\'"]+\.\w+)[\'"]?', last_message)
                if path_match:
                    return {
                        "type": "tool_calls",
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps({"path": path_match.group(1)})
                            }
                        }]
                    }
        
        if "列出" in last_message and "目录" in last_message:
            path_match = re.search(r'[\'"]?(/[^\s\'"]+)[\'"]?', last_message)
            path = path_match.group(1) if path_match else "."
            return {
                "type": "tool_calls",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "list_directory",
                        "arguments": json.dumps({"path": path})
                    }
                }]
            }
        
        if "执行" in last_message or "运行" in last_message:
            return {
                "type": "tool_calls",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "exec_command",
                        "arguments": json.dumps({"command": last_message.split("执行")[-1].split("运行")[-1].strip()})
                    }
                }]
            }
        
        # 普通对话
        return {
            "type": "text",
            "content": f"我理解你说的是: {messages[-1]['content']}\n\n如果你需要我执行操作，请明确告诉我，比如:\n- 读取 /path/to/file 文件\n- 列出 /path/to/directory 目录\n- 执行命令: ls -la"
        }
    
    async def _execute_tool_call(self, tool_call: Dict) -> Dict:
        """执行工具调用"""
        try:
            function_name = tool_call["function"]["name"]
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                arguments = {}
                logger.warning(f"工具参数 JSON 解析失败: {tool_call['function']['arguments']}")
            
            logger.info(f"🔧 执行工具: {function_name}({arguments})")
            
            result = await tool_registry.execute(function_name, arguments)
            
            return {
                "tool_call_id": tool_call["id"],
                "function_name": function_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {
                "tool_call_id": tool_call.get("id", "unknown"),
                "error": str(e)
            }
    
    async def chat(self, user_message: str, system_prompt: str = None, context: Dict = None) -> AsyncGenerator[Dict, None]:
        """
        对话主循环 - 支持工具调用
        
        Yields:
            Dict: 包含 type 和 content 的事件
        """
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT}
        ]
        
        # 添加历史上下文
        if self.conversation_history:
            messages.extend(self.conversation_history[-10:])  # 保留最近10条
        
        # 添加用户消息
        messages.append({"role": "user", "content": user_message})
        
        # 获取工具定义
        tools = self._get_tools_schema("openai")
        
        # 工具调用循环
        tool_call_count = 0
        
        while tool_call_count < self.max_tool_calls:
            # 调用 LLM
            response = await self._call_llm(messages, tools)
            
            if response["type"] == "error":
                yield {"type": "error", "content": response.get("error", "未知错误")}
                return
            
            if response["type"] == "text":
                # 文本回复，结束循环
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": response["content"]})
                self._trim_history()  # 限制历史长度
                yield {"type": "text", "content": response["content"]}
                return
            
            if response["type"] == "tool_calls":
                # 有工具调用
                tool_calls = response["tool_calls"]
                
                # 发送工具调用事件
                yield {
                    "type": "tool_calls_start",
                    "tools": [tc["function"]["name"] for tc in tool_calls]
                }
                
                # 执行所有工具调用
                tool_results = []
                for tool_call in tool_calls:
                    yield {
                        "type": "tool_call",
                        "name": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"]
                    }
                    
                    result = await self._execute_tool_call(tool_call)
                    tool_results.append(result)
                    
                    yield {
                        "type": "tool_result",
                        "name": tool_call["function"]["name"],
                        "result": result
                    }
                
                # 将工具调用和结果加入消息历史
                messages.append({
                    "role": "assistant",
                    "tool_calls": tool_calls
                })
                
                for tr in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": json.dumps(tr.get("result", tr.get("error")), ensure_ascii=False)
                    })
                
                tool_call_count += 1
                
                # 发送继续处理事件
                yield {"type": "processing", "message": "正在处理工具结果..."}
        
        # 达到最大调用次数
        yield {
            "type": "warning",
            "content": f"已达到最大工具调用次数 ({self.max_tool_calls})，请简化您的请求。"
        }
    
    async def chat_simple(self, user_message: str) -> str:
        """简单对话接口 - 返回最终文本结果"""
        final_content = ""
        async for event in self.chat(user_message):
            if event["type"] == "text":
                final_content = event["content"]
            elif event["type"] == "error":
                final_content = f"错误: {event['content']}"
        
        return final_content


# 全局引擎实例
ai_engine = AIEngine()