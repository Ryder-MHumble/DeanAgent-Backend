#!/usr/bin/env python3
"""
SPA Crawler - 基于 Playwright 的通用 JavaScript 渲染爬虫

功能：
1. 支持 JavaScript 渲染的页面
2. 自动等待内容加载
3. 支持登录态持久化
4. 支持截图和 PDF 导出
5. 智能提取 JSON 数据

使用方法：
    source /tmp/playwright-env/bin/activate
    python3 spa_crawler.py --url "https://example.com" --output result.json
"""

import asyncio
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
except ImportError:
    print("请先安装 playwright: pip install playwright && playwright install chromium")
    raise


class SPACrawler:
    """通用 SPA 爬虫"""
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        user_data_dir: Optional[str] = None,
        proxy: Optional[str] = None,
    ):
        self.headless = headless
        self.timeout = timeout
        self.user_data_dir = user_data_dir
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            proxy={"server": self.proxy} if self.proxy else None,
        )
        
        # 创建持久化上下文（保存登录态）
        if self.user_data_dir:
            Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
            state_file = Path(f"{self.user_data_dir}/state.json")
            if state_file.exists():
                self.context = await self.browser.new_context(
                    storage_state=str(state_file)
                )
            else:
                self.context = await self.browser.new_context()
        else:
            self.context = await self.browser.new_context()
            
        # 设置默认超时
        self.context.set_default_timeout(self.timeout)
        
    async def save_state(self):
        """保存当前登录态"""
        if self.user_data_dir and self.context:
            state_file = Path(f"{self.user_data_dir}/state.json")
            await self.context.storage_state(path=str(state_file))
            print(f"✓ 登录态已保存: {state_file}")
            
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def crawl(
        self,
        url: str,
        wait_for: Optional[str] = None,
        wait_time: int = 2000,
        extract_json: bool = True,
        screenshot: bool = False,
        actions: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        爬取页面
        
        Args:
            url: 目标 URL
            wait_for: 等待特定元素出现（CSS 选择器）
            wait_time: 额外等待时间（毫秒）
            extract_json: 是否尝试提取 JSON 数据
            screenshot: 是否截图
            actions: 要执行的操作列表 [{"type": "click", "selector": "..."}, ...]
            
        Returns:
            {
                "url": "原始 URL",
                "title": "页面标题",
                "html": "完整 HTML",
                "json_data": {...},  # 提取的 JSON 数据
                "screenshot": "base64...",  # 截图（如果启用）
                "crawl_time": "ISO 时间戳",
            }
        """
        page = await self.context.new_page()
        
        try:
            # 导航到页面
            await page.goto(url, wait_until="networkidle")
            
            # 等待特定元素
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=self.timeout)
            
            # 额外等待
            await page.wait_for_timeout(wait_time)
            
            # 执行操作
            if actions:
                for action in actions:
                    if action["type"] == "click":
                        await page.click(action["selector"])
                        await page.wait_for_timeout(action.get("delay", 500))
                    elif action["type"] == "fill":
                        await page.fill(action["selector"], action["value"])
                    elif action["type"] == "scroll":
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(1000)
            
            # 获取页面信息
            title = await page.title()
            html = await page.content()
            
            result = {
                "url": url,
                "title": title,
                "html": html,
                "crawl_time": datetime.now().isoformat(),
            }
            
            # 提取 JSON 数据
            if extract_json:
                json_data = await self._extract_json(page, html)
                if json_data:
                    result["json_data"] = json_data
                    
            # 截图
            if screenshot:
                screenshot_bytes = await page.screenshot(full_page=True)
                import base64
                result["screenshot"] = base64.b64encode(screenshot_bytes).decode()
                
            return result
            
        finally:
            await page.close()
            
    async def _extract_json(self, page: Page, html: str) -> Optional[Dict]:
        """从页面中提取 JSON 数据"""
        
        # 常见的 JSON 数据模式
        patterns = [
            # Next.js
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            # Nuxt.js
            r'window\.__NUXT__\s*=\s*(\{.*?\})\s*;',
            # Vue.js
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;',
            # 通用 JSON 变量
            r'window\.__DATA__\s*=\s*(\{.*?\})\s*;',
            # Angular
            r'window\.(?:NG|ng)\s*=\s*(\{.*?\})\s*;',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return {"source": pattern[:30], "data": data}
                except json.JSONDecodeError:
                    continue
        
        # 尝试通过 JavaScript 直接获取
        try:
            data = await page.evaluate('''() => {
                // 尝试获取常见的数据对象
                if (window.__NEXT_DATA__) return window.__NEXT_DATA__;
                if (window.__NUXT__) return window.__NUXT__;
                if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                if (window.__DATA__) return window.__DATA__;
                if (window.__APOLLO_STATE__) return window.__APOLLO_STATE__;
                return null;
            }''')
            if data:
                return {"source": "window_object", "data": data}
        except:
            pass
            
        # 查找所有 script 标签中的 JSON
        json_objects = await page.evaluate('''() => {
            const scripts = document.querySelectorAll('script');
            const results = [];
            scripts.forEach(script => {
                const text = script.textContent;
                if (text && (text.startsWith('{') || text.startsWith('['))) {
                    try {
                        results.push(JSON.parse(text));
                    } catch {}
                }
            });
            return results.length > 0 ? results : null;
        }''')
        
        if json_objects:
            return {"source": "script_tags", "data": json_objects}
            
        return None

    async def crawl_list(
        self,
        url: str,
        item_selector: str,
        fields: Dict[str, str],
        next_button: Optional[str] = None,
        max_pages: int = 10,
    ) -> List[Dict]:
        """
        爬取列表页面
        
        Args:
            url: 列表页 URL
            item_selector: 列表项选择器
            fields: 字段映射 {"field_name": "css_selector"}
            next_button: 下一页按钮选择器
            max_pages: 最大页数
            
        Returns:
            列表数据
        """
        page = await self.context.new_page()
        results = []
        
        try:
            await page.goto(url, wait_until="networkidle")
            
            for page_num in range(max_pages):
                await page.wait_for_selector(item_selector, timeout=self.timeout)
                await page.wait_for_timeout(1000)
                
                # 提取数据
                items = await page.evaluate(f'''() => {{
                    const items = document.querySelectorAll('{item_selector}');
                    return Array.from(items).map(item => {{
                        const result = {{}};
                        {"".join(f"result['{k}'] = item.querySelector('{v}')?.textContent?.trim() || '';" for k, v in fields.items())}
                        return result;
                    }});
                }}''')
                
                results.extend(items)
                print(f"Page {page_num + 1}: Found {len(items)} items")
                
                # 点击下一页
                if next_button and page_num < max_pages - 1:
                    next_btn = page.locator(next_button)
                    if await next_btn.count() > 0:
                        await next_btn.click()
                        await page.wait_for_timeout(2000)
                    else:
                        break
                else:
                    break
                        
            return results
            
        finally:
            await page.close()


async def main():
    parser = argparse.ArgumentParser(description="SPA 爬虫")
    parser.add_argument("--url", required=True, help="目标 URL")
    parser.add_argument("--output", default="output.json", help="输出文件")
    parser.add_argument("--wait-for", help="等待的 CSS 选择器")
    parser.add_argument("--wait-time", type=int, default=2000, help="等待时间(ms)")
    parser.add_argument("--screenshot", action="store_true", help="截图")
    parser.add_argument("--user-data-dir", help="用户数据目录(保存登录态)")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式")
    
    args = parser.parse_args()
    
    crawler = SPACrawler(
        headless=args.headless,
        user_data_dir=args.user_data_dir,
    )
    
    await crawler.start()
    
    try:
        result = await crawler.crawl(
            url=args.url,
            wait_for=args.wait_for,
            wait_time=args.wait_time,
            screenshot=args.screenshot,
        )
        
        # 保存结果
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            
        print(f"✓ 爬取完成: {output_path}")
        print(f"  Title: {result['title']}")
        if "json_data" in result:
            print(f"  JSON data: {list(result['json_data'].keys())}")
            
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
