#!/usr/bin/env python3
"""
天池平台爬虫 - 使用 Playwright 处理 JavaScript 渲染

使用方法:
    source /tmp/playwright-env/bin/activate
    python3 crawler_tianchi.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/data/dataset/excellent_20260425/lib")
from spa_crawler import SPACrawler


async def crawl_tianchi():
    """爬取天池竞赛排行榜"""
    
    output_dir = Path("/data/dataset/excellent_20260425/ai_competitions/tianchi_data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    crawler = SPACrawler(headless=True, user_data_dir=str(output_dir / "browser_data"))
    await crawler.start()
    
    try:
        # 天池竞赛列表
        competitions = [
            {
                "name": "阿里云天池大赛",
                "url": "https://tianchi.aliyun.com/competition",
                "list_selector": ".competition-item, .comp-item, [class*='competition']",
            }
        ]
        
        results = {
            "source": "tianchi",
            "crawl_time": datetime.now().isoformat(),
            "competitions": [],
        }
        
        # 爬取竞赛列表页
        print("正在爬取天池竞赛列表...")
        page_result = await crawler.crawl(
            url="https://tianchi.aliyun.com/competition",
            wait_time=3000,
            screenshot=True,
        )
        
        # 保存截图
        if "screenshot" in page_result:
            import base64
            screenshot_path = output_dir / "tianchi_list.png"
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(page_result["screenshot"]))
            print(f"✓ 截图已保存: {screenshot_path}")
        
        # 从页面中提取竞赛数据
        html = page_result.get("html", "")
        
        # 使用正则提取竞赛信息
        import re
        
        # 提取竞赛 ID
        comp_ids = re.findall(r'competition/entrance/(\d+)', html)
        comp_ids = list(set(comp_ids))[:20]  # 去重，取前20个
        
        print(f"找到 {len(comp_ids)} 个竞赛 ID")
        
        # 爬取每个竞赛的排行榜
        for comp_id in comp_ids[:5]:  # 先爬取前5个
            print(f"\n正在爬取竞赛 {comp_id}...")
            
            ranking_url = f"https://tianchi.aliyun.com/competition/entrance/{comp_id}/rankingList"
            
            try:
                ranking_result = await crawler.crawl(
                    url=ranking_url,
                    wait_for=".ranking-list, table, [class*='rank']",
                    wait_time=3000,
                    screenshot=True,
                )
                
                # 提取排行榜数据
                ranking_html = ranking_result.get("html", "")
                
                # 查找排名数据
                ranks = re.findall(r'(\d+).*?<td[^>]*>([^<]+)</td>', ranking_html[:10000])
                
                comp_data = {
                    "competition_id": comp_id,
                    "url": ranking_url,
                    "title": ranking_result.get("title", ""),
                    "ranking_data": ranks[:20] if ranks else [],
                }
                
                results["competitions"].append(comp_data)
                print(f"  ✓ 竞赛 {comp_id}: 找到 {len(ranks)} 条排名数据")
                
                # 保存截图
                if "screenshot" in ranking_result:
                    import base64
                    screenshot_path = output_dir / f"competition_{comp_id}.png"
                    with open(screenshot_path, "wb") as f:
                        f.write(base64.b64decode(ranking_result["screenshot"]))
                
                # 避免请求过快
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"  ✗ 竞赛 {comp_id} 爬取失败: {e}")
        
        # 保存结果
        output_file = output_dir / "results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✓ 天池数据已保存: {output_file}")
        print(f"  竞赛数: {len(results['competitions'])}")
        
        return results
        
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(crawl_tianchi())
