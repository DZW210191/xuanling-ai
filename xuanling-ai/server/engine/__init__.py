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
- 网络搜索：搜索网络信息（需要配置API Key）

## 重要提示
- 如果工具调用失败或不可用，请直接用你的知识回复用户，不要卡住
- 如果用户请求需要实时信息但你无法搜索，请诚实地告诉用户，并提供基于你知识的一般性回答
- 始终保持回复有帮助，即使工具不可用

## 工作方式
1. 理解用户需求
2. 选择合适的工具（如果可用）
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
        # 检查 API Key
        if not self.api_key or self.api_key == "test-key":
            return {
                "type": "error",
                "content": "⚠️ API Key 未配置，请在系统设置中配置 API Key 后重试。",
                "error": "API_KEY_NOT_CONFIGURED"
            }
        
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
    
    def _clean_messages_for_api(self, messages: List[Dict]) -> List[Dict]:
        """清理消息列表，移除不完整的工具调用"""
        cleaned = []
        pending_tool_calls = {}  # tool_call_id -> tool_call
        
        for msg in messages:
            role = msg.get("role")
            
            # 如果是 assistant 且有 tool_calls，记录待响应的调用
            if role == "assistant" and "tool_calls" in msg:
                for tc in msg.get("tool_calls", []):
                    pending_tool_calls[tc["id"]] = tc
                cleaned.append(msg)
            
            # 如果是 tool 响应，从待处理列表中移除
            elif role == "tool":
                tc_id = msg.get("tool_call_id")
                if tc_id in pending_tool_calls:
                    del pending_tool_calls[tc_id]
                cleaned.append(msg)
            
            else:
                cleaned.append(msg)
        
        # 如果还有未响应的 tool_calls，移除最后的 assistant 消息
        if pending_tool_calls:
            # 从后向前移除不完整的工具调用
            while cleaned and cleaned[-1].get("role") == "assistant" and "tool_calls" in cleaned[-1]:
                cleaned.pop()
        
        return cleaned
    
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
        
        # 添加历史上下文（清理不完整的工具调用）
        if self.conversation_history:
            history = self.conversation_history[-10:]
            history = self._clean_messages_for_api(history)
            messages.extend(history)
        
        # 添加用户消息
        messages.append({"role": "user", "content": user_message})
        
        # 获取工具定义
        tools = self._get_tools_schema("openai")
        
        # 工具调用循环
        tool_call_count = 0
        final_assistant_content = None  # 记录最终的助手回复
        all_tool_calls = []  # 记录所有工具调用
        
        while tool_call_count < self.max_tool_calls:
            # 调用 LLM
            response = await self._call_llm(messages, tools)
            
            if response["type"] == "error":
                yield {"type": "error", "content": response.get("error", "未知错误")}
                return
            
            if response["type"] == "text":
                # 文本回复，结束循环
                final_assistant_content = response["content"]
                yield {"type": "text", "content": response["content"]}
                break
            
            if response["type"] == "tool_calls":
                # 有工具调用
                tool_calls = response["tool_calls"]
                
                # 记录所有工具调用
                all_tool_calls.extend(tool_calls)
                
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
                
                # 如果达到最大调用次数，记录警告
                if tool_call_count >= self.max_tool_calls:
                    yield {
                        "type": "warning",
                        "content": f"已达到最大工具调用次数 ({self.max_tool_calls})，请简化您的请求。"
                    }
        
        # 统一更新历史记录
        # 只有在有最终回复时才更新历史（避免存储不完整的工具调用）
        if final_assistant_content:
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": final_assistant_content})
            self._trim_history()
        elif tool_call_count > 0 and all_tool_calls:
            # 如果只有工具调用但没有最终回复，记录用户消息但不记录不完整的工具调用
            # 这样下次对话可以从头开始
            logger.warning("工具调用未完成，跳过历史记录更新")
    
    async def chat_simple(self, user_message: str) -> str:
        """简单对话接口 - 返回最终文本结果"""
        final_content = ""
        has_error = False
        error_msg = ""
        
        async for event in self.chat(user_message):
            if event["type"] == "text":
                final_content = event["content"]
            elif event["type"] == "error":
                has_error = True
                error_msg = event.get("content", "未知错误")
                final_content = f"错误: {error_msg}"
            elif event["type"] == "tool_result":
                # 检查工具是否失败
                result = event.get("result", {})
                if result.get("success") == False and result.get("error"):
                    error_msg = result.get("error", "")
                    logger.warning(f"工具调用失败: {error_msg}")
        
        # 如果没有收到最终回复但有错误，返回错误信息
        if not final_content and has_error:
            return f"抱歉，处理请求时遇到问题: {error_msg}"
        
        # 如果完全没有回复
        if not final_content:
            return "抱歉，未收到有效回复。请稍后重试或简化您的请求。"
        
        return final_content


# 全局引擎实例
ai_engine = AIEngine()