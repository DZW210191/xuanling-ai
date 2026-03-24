#!/usr/bin/env python3
"""
浏览器模块测试脚本
测试网页搜索和抓取功能
"""
import asyncio
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from browser import browser_manager, web_search, web_scrape


async def test_browser():
    """测试浏览器功能"""
    print("=" * 50)
    print("🧪 浏览器模块测试")
    print("=" * 50)
    
    try:
        # 1. 初始化浏览器
        print("\n📍 步骤 1: 初始化浏览器...")
        success = await browser_manager.initialize(headless=True)
        if not success:
            print("❌ 浏览器初始化失败")
            return
        print("✅ 浏览器初始化成功")
        
        # 2. 打开测试网页
        print("\n📍 步骤 2: 打开测试网页...")
        result = await browser_manager.open("https://www.baidu.com")
        print(f"   URL: {result.get('url')}")
        print(f"   标题: {result.get('title')}")
        
        # 3. 获取页面快照
        print("\n📍 步骤 3: 获取页面快照...")
        snapshot = await browser_manager.snapshot(interactive_only=True)
        print(f"   元素数量: {len(snapshot.elements)}")
        print("   前 5 个元素:")
        for elem in snapshot.elements[:5]:
            print(f"     {elem.ref}: [{elem.type.value}] {elem.text[:30] if elem.text else ''}")
        
        # 4. 测试搜索功能
        print("\n📍 步骤 4: 测试搜索功能...")
        search_input = None
        for elem in snapshot.elements:
            if elem.type.value == "textbox" and "搜索" in elem.placeholder:
                search_input = elem.ref
                break
        
        if search_input:
            print(f"   找到搜索框: {search_input}")
            await browser_manager.fill(search_input, "Python 教程")
            print("   已输入搜索内容: Python 教程")
            
            # 按回车搜索
            await browser_manager.press("Enter")
            print("   已按回车搜索...")
            
            # 等待加载
            await asyncio.sleep(2)
            
            # 获取新的快照
            snapshot2 = await browser_manager.snapshot(interactive_only=True)
            print(f"   搜索结果页元素数: {len(snapshot2.elements)}")
            print(f"   当前 URL: {await browser_manager.get_url()}")
        
        # 5. 测试内容提取
        print("\n📍 步骤 5: 测试内容提取...")
        text_result = await browser_manager.get_text()
        print(f"   页面文本长度: {len(text_result.get('text', ''))} 字符")
        
        # 6. 测试截图
        print("\n📍 步骤 6: 测试截图...")
        screenshot_result = await browser_manager.screenshot(full_page=False)
        if screenshot_result.get("success"):
            print(f"   截图大小: {len(screenshot_result.get('base64', ''))} bytes (base64)")
        
        # 7. 测试 web_scrape
        print("\n📍 步骤 7: 测试网页抓取...")
        scrape_result = await web_scrape("https://example.com")
        if scrape_result.get("success"):
            data = scrape_result.get("data", {})
            print(f"   标题: {data.get('title')}")
            print(f"   文本长度: {len(data.get('text', ''))}")
            print(f"   链接数: {len(data.get('links', []))}")
        
        # 关闭浏览器
        print("\n📍 关闭浏览器...")
        await browser_manager.close()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        await browser_manager.close()


if __name__ == "__main__":
    asyncio.run(test_browser())