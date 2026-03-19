"""
Plugins - 插件系统
"""
from typing import Dict, Any, List
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """插件基类"""
    
    name: str = "base"
    
    @abstractmethod
    async def handle(self, message: dict) -> dict:
        """处理消息"""
        pass
    
    async def on_start(self):
        """启动时"""
        pass
    
    async def on_stop(self):
        """停止时"""
        pass


class FeishuPlugin(BasePlugin):
    """飞书插件"""
    
    name = "feishu"
    
    async def handle(self, message: dict) -> dict:
        """处理飞书消息"""
        return {"type": "text", "content": "消息已收到"}


class TelegramPlugin(BasePlugin):
    """Telegram 插件"""
    
    name = "telegram"
    
    async def handle(self, message: dict) -> dict:
        """处理 Telegram 消息"""
        return {"method": "sendMessage", "text": "消息已收到"}


class DiscordPlugin(BasePlugin):
    """Discord 插件"""
    
    name = "discord"
    
    async def handle(self, message: dict) -> dict:
        """处理 Discord 消息"""
        return {"content": "消息已收到"}


class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugins: List[str]):
        self.plugins: Dict[str, BasePlugin] = {}
        self._load_plugins(plugins)
    
    def _load_plugins(self, plugin_names: List[str]):
        """加载插件"""
        available = {
            "feishu": FeishuPlugin,
            "telegram": TelegramPlugin,
            "discord": DiscordPlugin
        }
        
        for name in plugin_names:
            if name in available:
                self.plugins[name] = available[name]()
    
    async def handle(self, platform: str, message: dict) -> dict:
        """处理消息"""
        plugin = self.plugins.get(platform)
        if plugin:
            return await plugin.handle(message)
        return {"error": "Plugin not found"}
    
    async def on_start(self):
        """启动所有插件"""
        for plugin in self.plugins.values():
            await plugin.on_start()
    
    async def on_stop(self):
        """停止所有插件"""
        for plugin in self.plugins.values():
            await plugin.on_stop()
