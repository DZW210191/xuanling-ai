"""
Model - 模型适配层
"""
from typing import List, Dict, Any
import aiohttp


class BaseModel:
    """模型基类"""
    
    def __init__(self, config: Dict):
        self.config = config
    
    async def chat(self, messages: List[Dict]) -> str:
        raise NotImplementedError


class MiniMaxModel(BaseModel):
    """MiniMax 模型"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.minimax.chat/v1")
        self.model = config.get("model", "MiniMax-M2.5")
    
    async def chat(self, messages: List[Dict]) -> str:
        """发送聊天请求"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    return f"API 错误: {resp.status}"


class OpenAIModel(BaseModel):
    """OpenAI 模型"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.model = config.get("model", "gpt-4")
    
    async def chat(self, messages: List[Dict]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    return f"API 错误: {resp.status}"


class MockModel(BaseModel):
    """模拟模型 - 用于测试"""
    
    async def chat(self, messages: List[Dict]) -> str:
        # 提取所有消息内容用于上下文
        context = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                continue
            context += f"{role}: {content}\n"
        
        last_msg = messages[-1]["content"] if messages else ""
        
        # 简单的上下文理解
        if "叫什么" in last_msg or "名字" in last_msg:
            # 从历史中找名字
            for msg in messages:
                content = msg.get("content", "")
                if "叫" in content and "我" in content:
                    # 提取名字
                    import re
                    match = re.search(r'叫(\w+)', content)
                    if match:
                        return f"你叫{match.group(1)}呀！"
            
            # 检查是否告诉过名字
            if "小明" in context:
                return "你叫小明呀！"
            elif "小红" in context:
                return "你叫小红呀！"
            elif "用户" in context:
                return "你之前告诉我你叫...抱歉，我再想想"
        
        if "你好" in last_msg:
            return "你好！有什么我可以帮你的吗？"
        
        if "帮助" in last_msg:
            return "我可以帮你：\n• 智能对话\n• 管理项目\n• 记忆信息\n• 执行任务"
        
        return f"我收到了: {last_msg[:30]}...\n\n(这是Mock模型回复，请配置真实API以获得更好的对话体验)"


class ModelRouter:
    """模型路由器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.provider = config.get("provider", "mock")
        self.model = self._create_model()
    
    def _create_model(self) -> BaseModel:
        provider = self.provider.lower()
        
        if provider == "minimax":
            return MiniMaxModel(self.config)
        elif provider == "openai":
            return OpenAIModel(self.config)
        else:
            return MockModel(self.config)
    
    async def chat(self, messages: List[Dict]) -> str:
        """聊天"""
        return await self.model.chat(messages)
