"""
玄灵AI 浏览器自动化模块
复刻 OpenClaw agent-browser 功能
支持: 网页导航、内容抓取、表单填写、截图、搜索
底层引擎: Playwright
"""
import os
import json
import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import hashlib

logger = logging.getLogger("玄灵AI.Browser")

# ============== 浏览器状态枚举 ==============

class BrowserStatus(str, Enum):
    """浏览器状态"""
    IDLE = "idle"
    NAVIGATING = "navigating"
    READY = "ready"
    ERROR = "error"
    CLOSED = "closed"


class ElementType(str, Enum):
    """元素类型"""
    BUTTON = "button"
    LINK = "link"
    TEXTBOX = "textbox"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    IMAGE = "image"
    TEXT = "text"
    HEADING = "heading"
    OTHER = "other"


# ============== 数据结构 ==============

@dataclass
class ElementInfo:
    """页面元素信息"""
    ref: str                    # 元素引用 (如 @e1, @e2)
    type: ElementType           # 元素类型
    tag: str                    # HTML 标签
    text: str = ""              # 文本内容
    name: str = ""              # 名称属性
    value: str = ""             # 值
    placeholder: str = ""       # 占位符
    href: str = ""              # 链接地址
    is_visible: bool = True     # 是否可见
    is_enabled: bool = True     # 是否可用
    is_checked: bool = False    # 是否选中
    selector: str = ""          # CSS 选择器
    bounds: Dict = field(default_factory=dict)  # 边界框
    
    def to_dict(self) -> Dict:
        return {
            "ref": self.ref,
            "type": self.type.value if isinstance(self.type, ElementType) else self.type,
            "tag": self.tag,
            "text": self.text[:100] if self.text else "",
            "name": self.name,
            "value": self.value,
            "placeholder": self.placeholder,
            "href": self.href,
            "is_visible": self.is_visible,
            "is_enabled": self.is_enabled,
            "is_checked": self.is_checked,
            "selector": self.selector
        }


@dataclass
class PageSnapshot:
    """页面快照"""
    url: str
    title: str
    elements: List[ElementInfo]
    text_content: str = ""
    html_content: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "title": self.title,
            "elements": [e.to_dict() for e in self.elements],
            "text_content": self.text_content[:5000] if self.text_content else "",
            "element_count": len(self.elements),
            "timestamp": self.timestamp
        }


@dataclass
class BrowserSession:
    """浏览器会话"""
    session_id: str
    status: BrowserStatus = BrowserStatus.IDLE
    current_url: str = ""
    page_title: str = ""
    created_at: str = ""
    last_activity: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "created_at": self.created_at,
            "last_activity": self.last_activity
        }


# ============== 浏览器管理器 ==============

class BrowserManager:
    """
    浏览器管理器 - 核心类
    封装 Playwright 提供统一的浏览器自动化接口
    """
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session: Optional[BrowserSession] = None
        self._element_cache: Dict[str, Any] = {}
        self._cookies: List[Dict] = []
        self._localStorage: Dict[str, Any] = {}
        self._is_initialized = False
        self._headless = True
        self._viewport = {"width": 1920, "height": 1080}
        self._timeout = 30000  # 30 秒
        
    async def initialize(self, headless: bool = True) -> bool:
        """初始化浏览器"""
        if self._is_initialized:
            return True
            
        try:
            from playwright.async_api import async_playwright
            
            self._headless = headless
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            self._context = await self._browser.new_context(
                viewport=self._viewport,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
                timezone_id="Asia/Shanghai"
            )
            
            self._page = await self._context.new_page()
            self._page.set_default_timeout(self._timeout)
            
            # 创建会话
            session_id = hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:8]
            self._session = BrowserSession(
                session_id=session_id,
                status=BrowserStatus.IDLE,
                created_at=datetime.now().isoformat()
            )
            
            self._is_initialized = True
            logger.info(f"✅ 浏览器初始化完成 (session: {session_id}, headless: {headless})")
            return True
            
        except ImportError:
            logger.error("❌ Playwright 未安装，请运行: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            logger.error(f"❌ 浏览器初始化失败: {e}")
            return False
    
    async def ensure_initialized(self) -> bool:
        """确保浏览器已初始化"""
        if not self._is_initialized:
            return await self.initialize()
        return True
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            
            self._is_initialized = False
            self._session = None
            self._element_cache.clear()
            logger.info("🛑 浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
    
    # ============== 导航操作 ==============
    
    async def open(self, url: str, wait_until: str = "networkidle") -> Dict:
        """
        打开网页
        
        Args:
            url: 网页地址
            wait_until: 等待条件 (load/domcontentloaded/networkidle)
        """
        if not await self.ensure_initialized():
            return {"success": False, "error": "浏览器未初始化"}
        
        try:
            # 自动添加协议
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            
            self._session.status = BrowserStatus.NAVIGATING
            
            await self._page.goto(url, wait_until=wait_until, timeout=self._timeout)
            
            self._session.current_url = self._page.url
            self._session.page_title = await self._page.title()
            self._session.status = BrowserStatus.READY
            self._session.last_activity = datetime.now().isoformat()
            
            # 清空元素缓存
            self._element_cache.clear()
            
            return {
                "success": True,
                "url": self._session.current_url,
                "title": self._session.page_title,
                "status": "ready"
            }
        except Exception as e:
            self._session.status = BrowserStatus.ERROR
            return {"success": False, "error": str(e)}
    
    async def back(self) -> Dict:
        """后退"""
        try:
            await self._page.go_back()
            self._session.current_url = self._page.url
            self._session.page_title = await self._page.title()
            self._element_cache.clear()
            return {"success": True, "url": self._session.current_url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def forward(self) -> Dict:
        """前进"""
        try:
            await self._page.go_forward()
            self._session.current_url = self._page.url
            self._session.page_title = await self._page.title()
            self._element_cache.clear()
            return {"success": True, "url": self._session.current_url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def reload(self) -> Dict:
        """刷新页面"""
        try:
            await self._page.reload()
            self._session.current_url = self._page.url
            self._session.page_title = await self._page.title()
            self._element_cache.clear()
            return {"success": True, "url": self._session.current_url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== 页面快照 ==============
    
    async def snapshot(self, interactive_only: bool = False, scope: str = None) -> PageSnapshot:
        """
        获取页面快照
        
        Args:
            interactive_only: 仅返回可交互元素
            scope: CSS 选择器限定范围
        """
        if not self._page:
            return PageSnapshot(url="", title="", elements=[])
        
        try:
            elements = []
            element_index = 0
            
            # 获取所有元素的选择器
            selectors = [
                "a", "button", "input", "select", "textarea", 
                "img", "h1", "h2", "h3", "h4", "h5", "h6",
                "[role='button']", "[role='link']", "[role='textbox']",
                "[onclick]", "[tabindex]"
            ]
            
            selector_str = ", ".join(selectors)
            if scope:
                selector_str = f"{scope} {selector_str}"
            
            # 获取元素列表
            handles = await self._page.query_selector_all(selector_str)
            
            for handle in handles:
                try:
                    # 获取元素信息
                    tag_name = await handle.evaluate("el => el.tagName.toLowerCase()")
                    is_visible = await handle.is_visible()
                    
                    # 跳过隐藏元素
                    if not is_visible:
                        continue
                    
                    text = await handle.inner_text() or ""
                    name_attr = await handle.get_attribute("name") or ""
                    value_attr = await handle.get_attribute("value") or ""
                    placeholder = await handle.get_attribute("placeholder") or ""
                    href = await handle.get_attribute("href") or ""
                    input_type = await handle.get_attribute("type") or "text" if tag_name == "input" else None
                    
                    # 判断元素类型
                    elem_type = self._determine_element_type(tag_name, input_type)
                    
                    # 如果只要可交互元素，过滤掉非交互元素
                    if interactive_only and elem_type in [ElementType.TEXT, ElementType.HEADING, ElementType.IMAGE]:
                        continue
                    
                    # 生成引用
                    element_index += 1
                    ref = f"@e{element_index}"
                    
                    # 存储元素句柄
                    self._element_cache[ref] = handle
                    
                    # 获取边界框
                    bounds = await handle.bounding_box() or {}
                    
                    # 检查状态
                    is_enabled = await handle.is_enabled() if tag_name in ["button", "input", "select", "textarea"] else True
                    is_checked = await handle.is_checked() if tag_name in ["input"] and await handle.get_attribute("type") in ["checkbox", "radio"] else False
                    
                    elements.append(ElementInfo(
                        ref=ref,
                        type=elem_type,
                        tag=tag_name,
                        text=text.strip()[:100],
                        name=name_attr,
                        value=value_attr,
                        placeholder=placeholder,
                        href=href,
                        is_visible=is_visible,
                        is_enabled=is_enabled,
                        is_checked=is_checked,
                        selector=await self._generate_selector(handle, tag_name),
                        bounds=bounds
                    ))
                    
                except Exception as e:
                    logger.debug(f"获取元素信息失败: {e}")
                    continue
            
            # 获取页面文本内容
            text_content = await self._page.inner_text("body") or ""
            
            return PageSnapshot(
                url=self._page.url,
                title=await self._page.title() or "",
                elements=elements,
                text_content=text_content,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"获取快照失败: {e}")
            return PageSnapshot(url="", title="", elements=[])
    
    def _determine_element_type(self, tag: str, input_type: str = None) -> ElementType:
        """判断元素类型"""
        type_map = {
            "button": ElementType.BUTTON,
            "a": ElementType.LINK,
            "img": ElementType.IMAGE,
            "select": ElementType.SELECT,
            "textarea": ElementType.TEXTBOX,
            "h1": ElementType.HEADING,
            "h2": ElementType.HEADING,
            "h3": ElementType.HEADING,
            "h4": ElementType.HEADING,
            "h5": ElementType.HEADING,
            "h6": ElementType.HEADING,
        }
        
        if tag in type_map:
            return type_map[tag]
        
        if tag == "input":
            if input_type == "checkbox":
                return ElementType.CHECKBOX
            elif input_type == "radio":
                return ElementType.RADIO
            return ElementType.TEXTBOX
        
        return ElementType.OTHER
    
    async def _generate_selector(self, handle, tag: str) -> str:
        """生成元素选择器"""
        try:
            # 尝试 ID
            elem_id = await handle.get_attribute("id")
            if elem_id:
                return f"#{elem_id}"
            
            # 尝试 name
            name = await handle.get_attribute("name")
            if name:
                return f"{tag}[name='{name}']"
            
            # 尝试 class
            classes = await handle.get_attribute("class")
            if classes:
                first_class = classes.split()[0]
                return f"{tag}.{first_class}"
            
            # 尝试 data 属性
            for attr in ["data-testid", "data-id", "data-testid"]:
                val = await handle.get_attribute(attr)
                if val:
                    return f"[{attr}='{val}']"
            
            return tag
        except:
            return tag
    
    # ============== 交互操作 ==============
    
    async def click(self, ref: str) -> Dict:
        """点击元素"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在，请先获取快照"}
        
        try:
            handle = self._element_cache[ref]
            await handle.click()
            
            # 等待页面稳定
            await asyncio.sleep(0.5)
            
            self._session.current_url = self._page.url
            self._session.last_activity = datetime.now().isoformat()
            
            # 清空缓存（页面可能已变化）
            self._element_cache.clear()
            
            return {"success": True, "ref": ref}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def fill(self, ref: str, text: str) -> Dict:
        """填写输入框"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在，请先获取快照"}
        
        try:
            handle = self._element_cache[ref]
            await handle.fill(text)
            self._session.last_activity = datetime.now().isoformat()
            return {"success": True, "ref": ref, "value": text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def type_text(self, ref: str, text: str, delay: int = 50) -> Dict:
        """逐字输入"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在"}
        
        try:
            handle = self._element_cache[ref]
            await handle.type(text, delay=delay)
            return {"success": True, "ref": ref}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def press(self, key: str) -> Dict:
        """按键"""
        try:
            await self._page.keyboard.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def hover(self, ref: str) -> Dict:
        """悬停"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在"}
        
        try:
            handle = self._element_cache[ref]
            await handle.hover()
            return {"success": True, "ref": ref}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def select_option(self, ref: str, value: str) -> Dict:
        """选择下拉选项"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在"}
        
        try:
            handle = self._element_cache[ref]
            await handle.select_option(value=value)
            return {"success": True, "ref": ref, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def check(self, ref: str) -> Dict:
        """勾选复选框"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在"}
        
        try:
            handle = self._element_cache[ref]
            await handle.check()
            return {"success": True, "ref": ref}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def uncheck(self, ref: str) -> Dict:
        """取消勾选"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在"}
        
        try:
            handle = self._element_cache[ref]
            await handle.uncheck()
            return {"success": True, "ref": ref}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def scroll(self, direction: str, distance: int = 300) -> Dict:
        """滚动页面"""
        try:
            if direction == "down":
                await self._page.mouse.wheel(0, distance)
            elif direction == "up":
                await self._page.mouse.wheel(0, -distance)
            elif direction == "left":
                await self._page.mouse.wheel(-distance, 0)
            elif direction == "right":
                await self._page.mouse.wheel(distance, 0)
            
            return {"success": True, "direction": direction, "distance": distance}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== 内容提取 ==============
    
    async def get_text(self, ref: str = None, selector: str = None) -> Dict:
        """获取元素文本"""
        try:
            if ref and ref in self._element_cache:
                handle = self._element_cache[ref]
                text = await handle.inner_text()
            elif selector:
                text = await self._page.inner_text(selector)
            else:
                text = await self._page.inner_text("body")
            
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_html(self, ref: str = None, selector: str = None) -> Dict:
        """获取 HTML 内容"""
        try:
            if ref and ref in self._element_cache:
                handle = self._element_cache[ref]
                html = await handle.inner_html()
            elif selector:
                html = await self._page.inner_html(selector)
            else:
                html = await self._page.content()
            
            return {"success": True, "html": html[:50000]}  # 限制大小
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_attribute(self, ref: str, attr: str) -> Dict:
        """获取元素属性"""
        if ref not in self._element_cache:
            return {"success": False, "error": f"元素引用 {ref} 不存在"}
        
        try:
            handle = self._element_cache[ref]
            value = await handle.get_attribute(attr)
            return {"success": True, "attribute": attr, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_url(self) -> str:
        """获取当前 URL"""
        return self._page.url if self._page else ""
    
    async def get_title(self) -> str:
        """获取页面标题"""
        return await self._page.title() if self._page else ""
    
    async def query(self, selector: str) -> Dict:
        """CSS 选择器查询"""
        try:
            handles = await self._page.query_selector_all(selector)
            results = []
            for i, handle in enumerate(handles[:50]):  # 限制数量
                text = await handle.inner_text()
                results.append({
                    "index": i,
                    "text": text[:200] if text else ""
                })
            return {"success": True, "count": len(results), "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def xpath(self, expression: str) -> Dict:
        """XPath 查询"""
        try:
            handles = await self._page.locator(f"xpath={expression}").all()
            results = []
            for i, handle in enumerate(handles[:50]):
                text = await handle.inner_text()
                results.append({
                    "index": i,
                    "text": text[:200] if text else ""
                })
            return {"success": True, "count": len(results), "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== 截图和 PDF ==============
    
    async def screenshot(self, path: str = None, full_page: bool = False, selector: str = None) -> Dict:
        """截图"""
        try:
            if selector:
                handle = await self._page.query_selector(selector)
                if not handle:
                    return {"success": False, "error": f"选择器 {selector} 未找到元素"}
                screenshot_bytes = await handle.screenshot()
            else:
                screenshot_bytes = await self._page.screenshot(
                    path=path,
                    full_page=full_page
                )
            
            if path:
                return {"success": True, "path": path}
            else:
                import base64
                b64 = base64.b64encode(screenshot_bytes).decode()
                return {"success": True, "base64": b64, "format": "png"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def pdf(self, path: str) -> Dict:
        """导出 PDF"""
        try:
            await self._page.pdf(path=path, format="A4")
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== 等待操作 ==============
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> Dict:
        """等待元素出现"""
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def wait_for_url(self, pattern: str, timeout: int = 30000) -> Dict:
        """等待 URL 匹配"""
        try:
            await self._page.wait_for_url(f"*{pattern}*", timeout=timeout)
            return {"success": True, "pattern": pattern, "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def wait_for_load(self, state: str = "networkidle") -> Dict:
        """等待页面加载"""
        try:
            await self._page.wait_for_load_state(state)
            return {"success": True, "state": state}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def wait(self, milliseconds: int) -> Dict:
        """等待指定时间"""
        await asyncio.sleep(milliseconds / 1000)
        return {"success": True, "waited_ms": milliseconds}
    
    # ============== JavaScript 执行 ==============
    
    async def evaluate(self, script: str) -> Dict:
        """执行 JavaScript"""
        try:
            result = await self._page.evaluate(script)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== 状态管理 ==============
    
    async def get_cookies(self) -> Dict:
        """获取所有 Cookies"""
        try:
            cookies = await self._context.cookies()
            return {"success": True, "cookies": cookies}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def set_cookie(self, name: str, value: str, domain: str = None) -> Dict:
        """设置 Cookie"""
        try:
            cookie = {"name": name, "value": value}
            if domain:
                cookie["domain"] = domain
            await self._context.add_cookies([cookie])
            return {"success": True, "name": name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def clear_cookies(self) -> Dict:
        """清除所有 Cookies"""
        try:
            await self._context.clear_cookies()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict:
        """获取浏览器状态"""
        if not self._session:
            return {"status": "not_initialized"}
        return {
            "status": self._session.status.value,
            "url": self._session.current_url,
            "title": self._session.page_title,
            "session_id": self._session.session_id,
            "is_initialized": self._is_initialized
        }


# ============== 全局浏览器实例 ==============

browser_manager = BrowserManager()


# ============== 便捷函数 ==============

async def browser_open(url: str) -> Dict:
    """打开网页"""
    return await browser_manager.open(url)


async def browser_snapshot(interactive_only: bool = True) -> PageSnapshot:
    """获取页面快照"""
    return await browser_manager.snapshot(interactive_only)


async def browser_click(ref: str) -> Dict:
    """点击元素"""
    return await browser_manager.click(ref)


async def browser_fill(ref: str, text: str) -> Dict:
    """填写输入框"""
    return await browser_manager.fill(ref, text)


async def browser_get_text(selector: str = None) -> Dict:
    """获取文本"""
    return await browser_manager.get_text(selector=selector)


async def browser_screenshot(path: str = None, full_page: bool = False) -> Dict:
    """截图"""
    return await browser_manager.screenshot(path, full_page)


async def browser_close() -> Dict:
    """关闭浏览器"""
    await browser_manager.close()
    return {"success": True, "message": "浏览器已关闭"}


# ============== 网页搜索功能 ==============

async def web_search(
    query: str, 
    engine: str = "google", 
    max_results: int = 10,
    headless: bool = True
) -> Dict:
    """
    网页搜索
    
    Args:
        query: 搜索关键词
        engine: 搜索引擎 (google/bing/baidu)
        max_results: 最大结果数
        headless: 无头模式
    """
    # 搜索引擎 URL 模板
    search_urls = {
        "google": "https://www.google.com/search?q={query}&num={num}",
        "bing": "https://www.bing.com/search?q={query}&count={num}",
        "baidu": "https://www.baidu.com/s?wd={query}&rn={num}",
        "duckduckgo": "https://duckduckgo.com/?q={query}"
    }
    
    if engine not in search_urls:
        return {"success": False, "error": f"不支持的搜索引擎: {engine}"}
    
    try:
        # 初始化浏览器
        if not await browser_manager.ensure_initialized():
            return {"success": False, "error": "浏览器初始化失败"}
        
        # 构建搜索 URL
        url = search_urls[engine].format(
            query=query.replace(" ", "+"),
            num=max_results
        )
        
        # 打开搜索页面
        result = await browser_manager.open(url)
        if not result.get("success"):
            return result
        
        # 等待结果加载
        await asyncio.sleep(2)
        
        # 获取搜索结果
        snapshot = await browser_manager.snapshot(interactive_only=True)
        
        # 解析搜索结果
        results = []
        for elem in snapshot.elements:
            if elem.type == ElementType.LINK and elem.href:
                # 过滤掉导航链接
                if any(x in elem.href.lower() for x in ["google.com/search", "bing.com/search", "baidu.com/link?url"]):
                    continue
                
                # 提取搜索结果
                if elem.text and len(elem.text) > 10:
                    results.append({
                        "title": elem.text[:100],
                        "url": elem.href,
                        "snippet": ""
                    })
        
        # 如果结果太少，尝试从页面文本提取
        if len(results) < 3:
            text_content = snapshot.text_content
            # 简单的结果提取
            lines = text_content.split("\n")
            for line in lines:
                if "http" in line and len(line) > 20:
                    # 尝试提取 URL
                    urls = re.findall(r'https?://[^\s<>"]+', line)
                    for url in urls[:2]:
                        if url not in [r["url"] for r in results]:
                            results.append({
                                "title": line[:80],
                                "url": url,
                                "snippet": ""
                            })
        
        return {
            "success": True,
            "query": query,
            "engine": engine,
            "results": results[:max_results],
            "count": len(results[:max_results])
        }
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return {"success": False, "error": str(e)}


async def web_scrape(
    url: str,
    extract_links: bool = True,
    extract_images: bool = False,
    extract_text: bool = True
) -> Dict:
    """
    网页抓取
    
    Args:
        url: 网页地址
        extract_links: 提取链接
        extract_images: 提取图片
        extract_text: 提取文本
    """
    try:
        # 初始化浏览器
        if not await browser_manager.ensure_initialized():
            return {"success": False, "error": "浏览器初始化失败"}
        
        # 打开页面
        result = await browser_manager.open(url)
        if not result.get("success"):
            return result
        
        # 等待页面加载
        await browser_manager.wait_for_load("networkidle")
        
        data = {
            "url": url,
            "title": await browser_manager.get_title(),
            "timestamp": datetime.now().isoformat()
        }
        
        # 提取文本
        if extract_text:
            text_result = await browser_manager.get_text()
            data["text"] = text_result.get("text", "")[:10000]
        
        # 提取链接
        if extract_links:
            links_result = await browser_manager.evaluate("""
                Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href
                })).filter(l => l.href && !l.href.startsWith('javascript:'))
            """)
            data["links"] = links_result.get("result", [])[:100]
        
        # 提取图片
        if extract_images:
            images_result = await browser_manager.evaluate("""
                Array.from(document.querySelectorAll('img')).map(img => ({
                    alt: img.alt,
                    src: img.src
                })).filter(i => i.src)
            """)
            data["images"] = images_result.get("result", [])[:50]
        
        # 提取元数据
        meta_result = await browser_manager.evaluate("""
            ({
                description: document.querySelector('meta[name="description"]')?.content || '',
                keywords: document.querySelector('meta[name="keywords"]')?.content || '',
                author: document.querySelector('meta[name="author"]')?.content || ''
            })
        """)
        data["meta"] = meta_result.get("result", {})
        
        return {"success": True, "data": data}
        
    except Exception as e:
        logger.error(f"抓取失败: {e}")
        return {"success": False, "error": str(e)}


async def web_screenshot(url: str, full_page: bool = True, save_path: str = None) -> Dict:
    """
    网页截图
    
    Args:
        url: 网页地址
        full_page: 全页截图
        save_path: 保存路径
    """
    try:
        # 初始化浏览器
        if not await browser_manager.ensure_initialized():
            return {"success": False, "error": "浏览器初始化失败"}
        
        # 打开页面
        result = await browser_manager.open(url)
        if not result.get("success"):
            return result
        
        # 等待页面加载
        await browser_manager.wait_for_load("networkidle")
        
        # 截图
        screenshot_result = await browser_manager.screenshot(save_path, full_page)
        
        return screenshot_result
        
    except Exception as e:
        return {"success": False, "error": str(e)}