"""
浏览器工具 - 注册到工具系统
支持网页导航、内容抓取、表单操作、截图、搜索
"""

from tools import tool_registry, ToolDefinition
from browser import (
    browser_manager, browser_open, browser_snapshot, 
    browser_click, browser_fill, browser_get_text, 
    browser_screenshot, browser_close,
    web_search, web_scrape, web_screenshot
)
import logging

logger = logging.getLogger("玄灵AI.BrowserTools")


# ============== 浏览器导航工具 ==============

async def tool_browser_open(url: str, wait_until: str = "networkidle") -> dict:
    """
    打开网页
    
    Args:
        url: 网页地址
        wait_until: 等待条件 (load/domcontentloaded/networkidle)
    """
    return await browser_manager.open(url, wait_until)


async def tool_browser_navigate(direction: str) -> dict:
    """
    浏览器导航
    
    Args:
        direction: 方向 (back/forward/reload)
    """
    if direction == "back":
        return await browser_manager.back()
    elif direction == "forward":
        return await browser_manager.forward()
    elif direction == "reload":
        return await browser_manager.reload()
    return {"success": False, "error": f"未知方向: {direction}"}


async def tool_browser_close() -> dict:
    """关闭浏览器"""
    await browser_manager.close()
    return {"success": True, "message": "浏览器已关闭"}


# ============== 页面快照工具 ==============

async def tool_browser_snapshot(interactive_only: bool = True, scope: str = None) -> dict:
    """
    获取页面快照
    
    Args:
        interactive_only: 仅返回可交互元素
        scope: CSS 选择器限定范围
    """
    snapshot = await browser_manager.snapshot(interactive_only, scope)
    return snapshot.to_dict()


# ============== 交互工具 ==============

async def tool_browser_click(ref: str) -> dict:
    """
    点击页面元素
    
    Args:
        ref: 元素引用 (如 @e1, @e2，从快照获取)
    """
    return await browser_manager.click(ref)


async def tool_browser_fill(ref: str, text: str) -> dict:
    """
    填写输入框
    
    Args:
        ref: 元素引用
        text: 要填写的文本
    """
    return await browser_manager.fill(ref, text)


async def tool_browser_type(ref: str, text: str, delay: int = 50) -> dict:
    """
    逐字输入
    
    Args:
        ref: 元素引用
        text: 要输入的文本
        delay: 每个字符间隔(毫秒)
    """
    return await browser_manager.type_text(ref, text, delay)


async def tool_browser_press(key: str) -> dict:
    """
    按键
    
    Args:
        key: 按键名称 (Enter/Escape/Tab/Backspace 或组合键如 Control+a)
    """
    return await browser_manager.press(key)


async def tool_browser_hover(ref: str) -> dict:
    """悬停在元素上"""
    return await browser_manager.hover(ref)


async def tool_browser_select(ref: str, value: str) -> dict:
    """
    选择下拉选项
    
    Args:
        ref: 元素引用
        value: 选项值
    """
    return await browser_manager.select_option(ref, value)


async def tool_browser_check(ref: str, checked: bool = True) -> dict:
    """
    勾选/取消勾选复选框
    
    Args:
        ref: 元素引用
        checked: 是否勾选
    """
    if checked:
        return await browser_manager.check(ref)
    else:
        return await browser_manager.uncheck(ref)


async def tool_browser_scroll(direction: str, distance: int = 300) -> dict:
    """
    滚动页面
    
    Args:
        direction: 方向 (up/down/left/right)
        distance: 滚动距离(像素)
    """
    return await browser_manager.scroll(direction, distance)


# ============== 内容提取工具 ==============

async def tool_browser_get_text(ref: str = None, selector: str = None) -> dict:
    """
    获取页面文本
    
    Args:
        ref: 元素引用 (可选)
        selector: CSS 选择器 (可选)
    """
    return await browser_manager.get_text(ref, selector)


async def tool_browser_get_html(ref: str = None, selector: str = None) -> dict:
    """
    获取页面 HTML
    
    Args:
        ref: 元素引用 (可选)
        selector: CSS 选择器 (可选)
    """
    return await browser_manager.get_html(ref, selector)


async def tool_browser_get_attr(ref: str, attr: str) -> dict:
    """
    获取元素属性
    
    Args:
        ref: 元素引用
        attr: 属性名称
    """
    return await browser_manager.get_attribute(ref, attr)


async def tool_browser_query(selector: str) -> dict:
    """
    CSS 选择器查询
    
    Args:
        selector: CSS 选择器
    """
    return await browser_manager.query(selector)


async def tool_browser_xpath(expression: str) -> dict:
    """
    XPath 查询
    
    Args:
        expression: XPath 表达式
    """
    return await browser_manager.xpath(expression)


# ============== 截图工具 ==============

async def tool_browser_screenshot(path: str = None, full_page: bool = False, selector: str = None) -> dict:
    """
    网页截图
    
    Args:
        path: 保存路径 (可选，不提供则返回 base64)
        full_page: 是否全页截图
        selector: 截取特定元素 (可选)
    """
    return await browser_manager.screenshot(path, full_page, selector)


async def tool_browser_pdf(path: str) -> dict:
    """
    导出 PDF
    
    Args:
        path: 保存路径
    """
    return await browser_manager.pdf(path)


# ============== 等待工具 ==============

async def tool_browser_wait(selector: str = None, timeout: int = 30000) -> dict:
    """
    等待元素出现
    
    Args:
        selector: CSS 选择器
        timeout: 超时时间(毫秒)
    """
    if selector:
        return await browser_manager.wait_for_selector(selector, timeout)
    else:
        return {"success": False, "error": "请提供选择器"}


async def tool_browser_wait_url(pattern: str, timeout: int = 30000) -> dict:
    """
    等待 URL 匹配
    
    Args:
        pattern: URL 匹配模式
        timeout: 超时时间(毫秒)
    """
    return await browser_manager.wait_for_url(pattern, timeout)


async def tool_browser_wait_load(state: str = "networkidle") -> dict:
    """
    等待页面加载
    
    Args:
        state: 加载状态 (load/domcontentloaded/networkidle)
    """
    return await browser_manager.wait_for_load(state)


async def tool_browser_sleep(milliseconds: int) -> dict:
    """
    等待指定时间
    
    Args:
        milliseconds: 等待时间(毫秒)
    """
    return await browser_manager.wait(milliseconds)


# ============== JavaScript 工具 ==============

async def tool_browser_eval(script: str) -> dict:
    """
    执行 JavaScript
    
    Args:
        script: JavaScript 代码
    """
    return await browser_manager.evaluate(script)


# ============== Cookie 工具 ==============

async def tool_browser_get_cookies() -> dict:
    """获取所有 Cookies"""
    return await browser_manager.get_cookies()


async def tool_browser_set_cookie(name: str, value: str, domain: str = None) -> dict:
    """
    设置 Cookie
    
    Args:
        name: Cookie 名称
        value: Cookie 值
        domain: 域名 (可选)
    """
    return await browser_manager.set_cookie(name, value, domain)


async def tool_browser_clear_cookies() -> dict:
    """清除所有 Cookies"""
    return await browser_manager.clear_cookies()


# ============== 网页搜索工具 ==============

async def tool_web_search(query: str, engine: str = "google", max_results: int = 10) -> dict:
    """
    网页搜索
    
    Args:
        query: 搜索关键词
        engine: 搜索引擎 (google/bing/baidu/duckduckgo)
        max_results: 最大结果数
    """
    return await web_search(query, engine, max_results)


# ============== 网页抓取工具 ==============

async def tool_web_scrape(
    url: str,
    extract_links: bool = True,
    extract_images: bool = False,
    extract_text: bool = True
) -> dict:
    """
    网页抓取
    
    Args:
        url: 网页地址
        extract_links: 提取链接
        extract_images: 提取图片
        extract_text: 提取文本
    """
    return await web_scrape(url, extract_links, extract_images, extract_text)


# ============== 状态工具 ==============

async def tool_browser_status() -> dict:
    """获取浏览器状态"""
    return browser_manager.get_status()


# ============== 注册所有工具 ==============

def register_browser_tools():
    """注册浏览器工具到工具系统"""
    
    # 导航工具
    tool_registry.register(ToolDefinition(
        name="browser_open",
        description="打开网页，返回页面 URL 和标题",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "网页地址"},
                "wait_until": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"], "default": "networkidle", "description": "等待条件"}
            },
            "required": ["url"]
        },
        handler=tool_browser_open,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_navigate",
        description="浏览器导航 (后退/前进/刷新)",
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["back", "forward", "reload"], "description": "导航方向"}
            },
            "required": ["direction"]
        },
        handler=tool_browser_navigate,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_close",
        description="关闭浏览器",
        parameters={"type": "object", "properties": {}},
        handler=tool_browser_close,
        category="browser"
    ))
    
    # 快照工具
    tool_registry.register(ToolDefinition(
        name="browser_snapshot",
        description="获取页面快照，返回可交互元素列表和元素引用(ref)，用于后续点击/填写操作",
        parameters={
            "type": "object",
            "properties": {
                "interactive_only": {"type": "boolean", "default": True, "description": "仅返回可交互元素"},
                "scope": {"type": "string", "description": "CSS 选择器限定范围 (可选)"}
            },
            "required": []
        },
        handler=tool_browser_snapshot,
        category="browser"
    ))
    
    # 交互工具
    tool_registry.register(ToolDefinition(
        name="browser_click",
        description="点击页面元素，使用快照返回的元素引用(如 @e1)",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "元素引用 (如 @e1)"}
            },
            "required": ["ref"]
        },
        handler=tool_browser_click,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_fill",
        description="填写输入框，清空现有内容后填入新文本",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "元素引用"},
                "text": {"type": "string", "description": "要填写的文本"}
            },
            "required": ["ref", "text"]
        },
        handler=tool_browser_fill,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_type",
        description="逐字输入文本，模拟人工输入",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "元素引用"},
                "text": {"type": "string", "description": "要输入的文本"},
                "delay": {"type": "integer", "default": 50, "description": "每个字符间隔(毫秒)"}
            },
            "required": ["ref", "text"]
        },
        handler=tool_browser_type,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_press",
        description="按键或组合键 (如 Enter/Escape/Control+a)",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "按键名称"}
            },
            "required": ["key"]
        },
        handler=tool_browser_press,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_scroll",
        description="滚动页面",
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "滚动方向"},
                "distance": {"type": "integer", "default": 300, "description": "滚动距离(像素)"}
            },
            "required": ["direction"]
        },
        handler=tool_browser_scroll,
        category="browser"
    ))
    
    # 内容提取
    tool_registry.register(ToolDefinition(
        name="browser_get_text",
        description="获取页面或元素的文本内容",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "元素引用 (可选)"},
                "selector": {"type": "string", "description": "CSS 选择器 (可选)"}
            },
            "required": []
        },
        handler=tool_browser_get_text,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_get_html",
        description="获取页面或元素的 HTML 内容",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "元素引用 (可选)"},
                "selector": {"type": "string", "description": "CSS 选择器 (可选)"}
            },
            "required": []
        },
        handler=tool_browser_get_html,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_query",
        description="CSS 选择器查询元素",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器"}
            },
            "required": ["selector"]
        },
        handler=tool_browser_query,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_xpath",
        description="XPath 查询元素",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "XPath 表达式"}
            },
            "required": ["expression"]
        },
        handler=tool_browser_xpath,
        category="browser"
    ))
    
    # 截图
    tool_registry.register(ToolDefinition(
        name="browser_screenshot",
        description="网页截图，返回 base64 或保存到文件",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "保存路径 (可选)"},
                "full_page": {"type": "boolean", "default": False, "description": "全页截图"},
                "selector": {"type": "string", "description": "截取特定元素 (可选)"}
            },
            "required": []
        },
        handler=tool_browser_screenshot,
        category="browser"
    ))
    
    # 等待
    tool_registry.register(ToolDefinition(
        name="browser_wait",
        description="等待元素出现或页面加载",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器"},
                "timeout": {"type": "integer", "default": 30000, "description": "超时时间(毫秒)"}
            },
            "required": ["selector"]
        },
        handler=tool_browser_wait,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_wait_load",
        description="等待页面加载完成",
        parameters={
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"], "default": "networkidle", "description": "加载状态"}
            },
            "required": []
        },
        handler=tool_browser_wait_load,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_sleep",
        description="等待指定时间",
        parameters={
            "type": "object",
            "properties": {
                "milliseconds": {"type": "integer", "description": "等待时间(毫秒)"}
            },
            "required": ["milliseconds"]
        },
        handler=tool_browser_sleep,
        category="browser"
    ))
    
    # JavaScript
    tool_registry.register(ToolDefinition(
        name="browser_eval",
        description="在页面中执行 JavaScript 代码",
        parameters={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript 代码"}
            },
            "required": ["script"]
        },
        handler=tool_browser_eval,
        category="browser"
    ))
    
    # Cookie
    tool_registry.register(ToolDefinition(
        name="browser_get_cookies",
        description="获取所有 Cookies",
        parameters={"type": "object", "properties": {}},
        handler=tool_browser_get_cookies,
        category="browser"
    ))
    
    tool_registry.register(ToolDefinition(
        name="browser_set_cookie",
        description="设置 Cookie",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Cookie 名称"},
                "value": {"type": "string", "description": "Cookie 值"},
                "domain": {"type": "string", "description": "域名 (可选)"}
            },
            "required": ["name", "value"]
        },
        handler=tool_browser_set_cookie,
        category="browser"
    ))
    
    # 网页搜索
    tool_registry.register(ToolDefinition(
        name="web_search",
        description="网页搜索，支持 Google/Bing/Baidu/DuckDuckGo",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "engine": {"type": "string", "enum": ["google", "bing", "baidu", "duckduckgo"], "default": "google", "description": "搜索引擎"},
                "max_results": {"type": "integer", "default": 10, "description": "最大结果数"}
            },
            "required": ["query"]
        },
        handler=tool_web_search,
        category="search"
    ))
    
    # 网页抓取
    tool_registry.register(ToolDefinition(
        name="web_scrape",
        description="抓取网页内容，提取文本、链接、图片等",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "网页地址"},
                "extract_links": {"type": "boolean", "default": True, "description": "提取链接"},
                "extract_images": {"type": "boolean", "default": False, "description": "提取图片"},
                "extract_text": {"type": "boolean", "default": True, "description": "提取文本"}
            },
            "required": ["url"]
        },
        handler=tool_web_scrape,
        category="browser"
    ))
    
    # 状态
    tool_registry.register(ToolDefinition(
        name="browser_status",
        description="获取浏览器当前状态",
        parameters={"type": "object", "properties": {}},
        handler=tool_browser_status,
        category="browser"
    ))
    
    logger.info(f"✅ 已注册 {20} 个浏览器工具")


# 自动注册
register_browser_tools()