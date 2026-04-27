#!/usr/bin/env python3
"""
华为竞赛平台爬虫 - 使用 Playwright 处理 JavaScript 渲染

使用方法:
    source /tmp/playwright-env/bin/activate
    python3 crawler_huawei.py
"""

import asyncio
import json
import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/data/dataset/excellent_20260425/lib")
from spa_crawler import SPACrawler


async def crawl_huawei():
    """爬取华为软件精英挑战赛"""
    
    output_dir = Path("/data/dataset/excellent_20260425/ai_competitions/huawei_data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    crawler = SPACrawler(headless=True, user_data_dir=str(output_dir / "browser_data"))
    await crawler.start()
    
    try:
        results = {
            "source": "huawei_competition",
            "crawl_time": datetime.now().isoformat(),
            "competitions": [],
        }
        
        # 华为竞赛列表页
        print("正在爬取华为竞赛列表...")
        list_result = await crawler.crawl(
            url="https://competition.huaweicloud.com/competitions",
            wait_time=3000,
            screenshot=True,
        )
        
        # 保存截图
        if "screenshot" in list_result:
            import base64
            screenshot_path = output_dir / "huawei_list.png"
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(list_result["screenshot"]))
            print(f"✓ 列表截图已保存: {screenshot_path}")
        
        # 提取竞赛链接
        html = list_result.get("html", "")
        
        # 华为竞赛平台 URL 格式: /information/{id}/introduction
        comp_links = re.findall(r'/information/(\d+)/introduction', html)
        comp_links = list(set(comp_links))[:10]
        
        print(f"找到 {len(comp_links)} 个竞赛 ID")
        
        # 爬取每个竞赛
        for comp_id in comp_links[:5]:
            print(f"\n正在爬取竞赛 {comp_id}...")
            
            comp_url = f"https://competition.huaweicloud.com/information/{comp_id}/introduction"
            
            try:
                comp_result = await crawler.crawl(
                    url=comp_url,
                    wait_time=2000,
                    screenshot=True,
                )
                
                comp_data = {
                    "competition_id": comp_id,
                    "url": comp_url,
                    "title": comp_result.get("title", ""),
                }
                
                # 尝试爬取排行榜
                ranking_url = f"https://competition.huaweicloud.com/information/{comp_id}/rankingList"
                
                try:
                    ranking_result = await crawler.crawl(
                        url=ranking_url,
                        wait_for="table, .ranking, [class*='rank']",
                        wait_time=3000,
                        screenshot=True,
                    )
                    
                    # 提取排行榜数据
                    ranking_html = ranking_result.get("html", "")
                    
                    # 查找表格数据
                    rows = re.findall(r'<tr[^>]*>.*?<td[^>]*>([^<]+)</td>.*?</tr>', ranking_html[:20000], re.DOTALL)
                    
                    comp_data["ranking_url"] = ranking_url
                    comp_data["ranking_preview"] = rows[:10] if rows else []
                    
                    # 保存排行榜截图
                    if "screenshot" in ranking_result:
                        import base64
                        screenshot_path = output_dir / f"ranking_{comp_id}.png"
                        with open(screenshot_path, "wb") as f:
                            f.write(base64.b64decode(ranking_result["screenshot"]))
                            print(f"  ✓ 排行榜截图已保存")
                    
                except Exception as e:
                    print(f"  排行榜爬取失败: {e}")
                    comp_data["ranking_error"] = str(e)
                
                results["competitions"].append(comp_data)
                print(f"  ✓ 竞赛 {comp_id}: {comp_data['title']}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"  ✗ 竞赛 {comp_id} 爬取失败: {e}")
        
        # 保存结果
        output_file = output_dir / "results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✓ 华为竞赛数据已保存: {output_file}")
        print(f"  竞赛数: {len(results['competitions'])}")
        
        return results
        
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(crawl_huawei())
