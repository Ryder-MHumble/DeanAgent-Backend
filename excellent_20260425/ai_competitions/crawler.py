#!/usr/bin/env python3
"""
AI竞赛获奖信息爬虫
爬取平台：CCF BDCI (DataFountain)、阿里天池、KDD Cup、华为软件精英挑战赛
"""

import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class AICompetitionCrawler:
    """AI竞赛爬虫基类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.competitions = []
        
    def delay(self, seconds: float = 1.0):
        """延迟，避免被封"""
        time.sleep(seconds)
        
    def save_results(self, output_path: str):
        """保存结果到JSON文件"""
        result = {
            "source": "ai_competitions",
            "crawl_time": datetime.now().isoformat(),
            "competitions": self.competitions
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {output_path}")
        return result


class DataFountainCrawler(AICompetitionCrawler):
    """DataFountain (CCF BDCI) 爬虫"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.datafountain.cn"
        
    def get_competition_list(self) -> List[Dict]:
        """获取竞赛列表"""
        competitions = []
        
        try:
            # 尝试访问竞赛列表页面
            url = f"{self.base_url}/competitions"
            print(f"正在访问: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找竞赛卡片 - DataFountain使用 .compt-item 类
            competition_items = soup.find_all('div', class_='compt-item')
            
            if not competition_items:
                # 尝试其他选择器
                competition_items = soup.find_all('a', href=re.compile(r'/competitions/\d+'))
            
            seen_ids = set()
            for item in competition_items[:8]:  # 限制爬取数量
                try:
                    # 查找标题链接
                    if item.name == 'a':
                        link = item
                    else:
                        link = item.find('a', class_='compt__title') or item.find('a', href=re.compile(r'/competitions/\d+'))
                    
                    if link and link.get('href'):
                        href = link['href']
                        # 提取竞赛ID避免重复
                        comp_id_match = re.search(r'/competitions/(\d+)', href)
                        if comp_id_match:
                            comp_id = comp_id_match.group(1)
                            if comp_id in seen_ids:
                                continue
                            seen_ids.add(comp_id)
                        
                        # 提取竞赛名称
                        title = link.get_text(strip=True) if link.name == 'a' else None
                        
                        comp_url = urljoin(self.base_url, href)
                        comp_info = self.get_competition_detail(comp_url, title)
                        if comp_info:
                            competitions.append(comp_info)
                        self.delay(1.5)
                except Exception as e:
                    print(f"处理竞赛卡片出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"获取DataFountain竞赛列表出错: {e}")
            
        return competitions
    
    def get_competition_detail(self, url: str, title: str = None) -> Optional[Dict]:
        """获取竞赛详情和排行榜"""
        try:
            print(f"  获取详情: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取竞赛名称
            if not title:
                title_elem = soup.find('h1') or soup.find('div', class_='title') or soup.find('a', class_='compt__title')
                title = title_elem.get_text(strip=True) if title_elem else "未知竞赛"
            
            # 尝试找到排行榜页面
            leaderboard_url = url.rstrip('/') + '/leaderboard'
            winners = self.get_leaderboard(leaderboard_url)
            
            # 提取年份
            year_match = re.search(r'20\d{2}', title)
            year = int(year_match.group()) if year_match else datetime.now().year
            
            return {
                "name": title,
                "platform": "DataFountain",
                "year": year,
                "tracks": [{
                    "track_name": "主赛道",
                    "winners": winners
                }]
            }
            
        except Exception as e:
            print(f"获取竞赛详情出错 {url}: {e}")
            return None
    
    def get_leaderboard(self, url: str) -> List[Dict]:
        """获取排行榜数据"""
        winners = []
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 查找排行榜表格
                table = soup.find('table') or soup.find('div', class_='leaderboard')
                if table:
                    rows = table.find_all('tr')[1:]  # 跳过表头
                    for i, row in enumerate(rows[:20]):  # 前20名
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            rank = i + 1
                            team_name = cols[1].get_text(strip=True) if len(cols) > 1 else f"Team_{rank}"
                            score = cols[-1].get_text(strip=True) if cols else "0"
                            
                            winners.append({
                                "rank": rank,
                                "team_name": team_name,
                                "members": [],
                                "score": float(score) if score.replace('.', '').isdigit() else 0
                            })
                            
        except Exception as e:
            print(f"获取排行榜出错 {url}: {e}")
            
        return winners


class TianchiCrawler(AICompetitionCrawler):
    """阿里天池爬虫"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://tianchi.aliyun.com"
        
    def get_competition_list(self) -> List[Dict]:
        """获取竞赛列表"""
        competitions = []
        
        try:
            print(f"正在访问天池: {self.base_url}")
            
            # 尝试API接口
            api_url = f"{self.base_url}/competition/proxy/list"
            params = {
                'page': 1,
                'pageSize': 20,
                'status': 5  # 已结束的竞赛
            }
            
            response = self.session.get(api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'data' in data and data['data']:
                        for comp in data['data'].get('list', [])[:5]:
                            comp_id = comp.get('competitionId')
                            if comp_id:
                                detail = self.get_competition_detail(str(comp_id))
                                if detail:
                                    competitions.append(detail)
                                self.delay(1.5)
                except Exception as api_error:
                    print(f"API方式失败: {api_error}")
            
            # 如果API失败，尝试HTML解析
            if not competitions:
                html_url = f"{self.base_url}/competition"
                response = self.session.get(html_url, timeout=30)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                comp_links = soup.find_all('a', href=re.compile(r'/competition/\d+'))
                seen = set()
                for link in comp_links[:5]:
                    href = link.get('href', '')
                    comp_id_match = re.search(r'\d+', href)
                    if comp_id_match:
                        comp_id = comp_id_match.group()
                        if comp_id not in seen:
                            seen.add(comp_id)
                            detail = self.get_competition_detail(comp_id)
                            if detail:
                                competitions.append(detail)
                            self.delay(1.5)
                        
        except Exception as e:
            print(f"获取天池竞赛列表出错: {e}")
            
        return competitions
    
    def get_competition_detail(self, comp_id: str) -> Optional[Dict]:
        """获取竞赛详情"""
        try:
            url = f"{self.base_url}/competition/{comp_id}"
            print(f"  获取天池竞赛详情: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取竞赛名称
            title_elem = soup.find('h1', class_='competition-title') or soup.find('h1')
            name = title_elem.get_text(strip=True) if title_elem else f"天池竞赛{comp_id}"
            
            # 提取年份
            year_match = re.search(r'20\d{2}', name)
            year = int(year_match.group()) if year_match else datetime.now().year
            
            # 获取排行榜
            winners = self.get_leaderboard(comp_id)
            
            return {
                "name": name,
                "platform": "天池",
                "year": year,
                "tracks": [{
                    "track_name": "主赛道",
                    "winners": winners
                }]
            }
            
        except Exception as e:
            print(f"获取天池竞赛详情出错: {e}")
            return None
    
    def get_leaderboard(self, comp_id: str) -> List[Dict]:
        """获取排行榜"""
        winners = []
        
        try:
            # 天池排行榜API
            api_url = f"{self.base_url}/competition/entrance/{comp_id}/rankList"
            response = self.session.get(api_url, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'data' in data:
                        for item in data['data'][:20]:
                            winners.append({
                                "rank": item.get('rank', 0),
                                "team_name": item.get('teamName', item.get('team_name', '')),
                                "members": item.get('members', []),
                                "score": item.get('score', 0)
                            })
                except:
                    pass
                    
        except Exception as e:
            print(f"获取天池排行榜出错: {e}")
            
        return winners


class KDDCupCrawler(AICompetitionCrawler):
    """KDD Cup 爬虫"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.kdd.org"
        
    def get_competition_list(self) -> List[Dict]:
        """获取KDD Cup竞赛列表"""
        competitions = []
        
        try:
            url = f"{self.base_url}/kdd-cup"
            print(f"正在访问KDD Cup: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # KDD Cup通常有历史竞赛列表
            comp_links = soup.find_all('a', href=re.compile(r'/kdd-cup|/kdd'))
            
            seen = set()
            for link in comp_links[:5]:
                href = link.get('href', '')
                full_url = urljoin(self.base_url, href)
                
                if full_url not in seen and 'kdd' in href.lower():
                    seen.add(full_url)
                    detail = self.get_competition_detail(full_url)
                    if detail:
                        competitions.append(detail)
                    self.delay(1.5)
                    
        except Exception as e:
            print(f"获取KDD Cup竞赛列表出错: {e}")
            
        return competitions
    
    def get_competition_detail(self, url: str) -> Optional[Dict]:
        """获取KDD Cup详情"""
        try:
            print(f"  获取KDD Cup详情: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取竞赛名称
            title_elem = soup.find('h1') or soup.find('h2', class_='title')
            name = title_elem.get_text(strip=True) if title_elem else "KDD Cup"
            
            # 提取年份
            year_match = re.search(r'20\d{2}', name)
            year = int(year_match.group()) if year_match else datetime.now().year
            
            # KDD Cup通常有多个赛道
            winners = self.get_leaderboard(url)
            
            return {
                "name": name,
                "platform": "KDD Cup",
                "year": year,
                "tracks": [{
                    "track_name": "主赛道",
                    "winners": winners
                }]
            }
            
        except Exception as e:
            print(f"获取KDD Cup详情出错: {e}")
            return None
    
    def get_leaderboard(self, url: str) -> List[Dict]:
        """获取排行榜"""
        winners = []
        
        try:
            response = self.session.get(url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找排行榜
            table = soup.find('table', class_='leaderboard') or soup.find('table')
            if table:
                rows = table.find_all('tr')[1:]
                for i, row in enumerate(rows[:20]):
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        winners.append({
                            "rank": i + 1,
                            "team_name": cols[1].get_text(strip=True),
                            "members": [],
                            "score": cols[-1].get_text(strip=True)
                        })
                        
        except Exception as e:
            print(f"获取KDD Cup排行榜出错: {e}")
            
        return winners


class HuaweiCompetitionCrawler(AICompetitionCrawler):
    """华为软件精英挑战赛爬虫"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://competition.huaweicloud.com"
        
    def get_competition_list(self) -> List[Dict]:
        """获取华为竞赛列表"""
        competitions = []
        
        try:
            url = self.base_url
            print(f"正在访问华为竞赛平台: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找竞赛链接
            comp_links = soup.find_all('a', href=re.compile(r'/competitions/\d+|/competition/'))
            
            seen = set()
            for link in comp_links[:5]:
                href = link.get('href', '')
                full_url = urljoin(self.base_url, href)
                
                if full_url not in seen:
                    seen.add(full_url)
                    detail = self.get_competition_detail(full_url)
                    if detail:
                        competitions.append(detail)
                    self.delay(1.5)
                    
        except Exception as e:
            print(f"获取华为竞赛列表出错: {e}")
            
        return competitions
    
    def get_competition_detail(self, url: str) -> Optional[Dict]:
        """获取华为竞赛详情"""
        try:
            print(f"  获取华为竞赛详情: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取竞赛名称
            title_elem = soup.find('h1') or soup.find('div', class_='competition-name')
            name = title_elem.get_text(strip=True) if title_elem else "华为竞赛"
            
            # 提取年份
            year_match = re.search(r'20\d{2}', name)
            year = int(year_match.group()) if year_match else datetime.now().year
            
            # 获取排行榜
            winners = self.get_leaderboard(url)
            
            return {
                "name": name,
                "platform": "华为软件精英挑战赛",
                "year": year,
                "tracks": [{
                    "track_name": "主赛道",
                    "winners": winners
                }]
            }
            
        except Exception as e:
            print(f"获取华为竞赛详情出错: {e}")
            return None
    
    def get_leaderboard(self, url: str) -> List[Dict]:
        """获取排行榜"""
        winners = []
        
        try:
            # 尝试排行榜API
            leaderboard_url = url.rstrip('/') + '/leaderboard'
            response = self.session.get(leaderboard_url, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    for item in data[:20]:
                        winners.append({
                            "rank": item.get('rank', 0),
                            "team_name": item.get('teamName', item.get('team_name', '')),
                            "members": [],
                            "score": item.get('score', 0)
                        })
                except:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    table = soup.find('table')
                    if table:
                        rows = table.find_all('tr')[1:]
                        for i, row in enumerate(rows[:20]):
                            cols = row.find_all('td')
                            if len(cols) >= 2:
                                winners.append({
                                    "rank": i + 1,
                                    "team_name": cols[1].get_text(strip=True),
                                    "members": [],
                                    "score": cols[-1].get_text(strip=True)
                                })
                                
        except Exception as e:
            print(f"获取华为排行榜出错: {e}")
            
        return winners


def crawl_all_competitions():
    """爬取所有平台的竞赛信息"""
    print("=" * 60)
    print("开始爬取AI竞赛获奖信息...")
    print("=" * 60)
    
    all_competitions = []
    
    # 1. DataFountain (CCF BDCI)
    print("\n[1/4] 正在爬取 DataFountain...")
    df_crawler = DataFountainCrawler()
    df_competitions = df_crawler.get_competition_list()
    all_competitions.extend(df_competitions)
    print(f"  获取到 {len(df_competitions)} 个竞赛")
    
    time.sleep(2)
    
    # 2. 天池
    print("\n[2/4] 正在爬取阿里天池...")
    tianchi_crawler = TianchiCrawler()
    tianchi_competitions = tianchi_crawler.get_competition_list()
    all_competitions.extend(tianchi_competitions)
    print(f"  获取到 {len(tianchi_competitions)} 个竞赛")
    
    time.sleep(2)
    
    # 3. KDD Cup
    print("\n[3/4] 正在爬取 KDD Cup...")
    kdd_crawler = KDDCupCrawler()
    kdd_competitions = kdd_crawler.get_competition_list()
    all_competitions.extend(kdd_competitions)
    print(f"  获取到 {len(kdd_competitions)} 个竞赛")
    
    time.sleep(2)
    
    # 4. 华为竞赛
    print("\n[4/4] 正在爬取华为软件精英挑战赛...")
    huawei_crawler = HuaweiCompetitionCrawler()
    huawei_competitions = huawei_crawler.get_competition_list()
    all_competitions.extend(huawei_competitions)
    print(f"  获取到 {len(huawei_competitions)} 个竞赛")
    
    print("\n" + "=" * 60)
    print(f"爬取完成！共获取 {len(all_competitions)} 个竞赛")
    print("=" * 60)
    
    return all_competitions


def main():
    """主函数"""
    output_path = "/data/dataset/excellent_20260425/ai_competitions/results.json"
    
    try:
        # 爬取所有竞赛
        competitions = crawl_all_competitions()
        
        # 保存结果
        result = {
            "source": "ai_competitions",
            "crawl_time": datetime.now().isoformat(),
            "competitions": competitions
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n结果已保存到: {output_path}")
        print(f"竞赛总数: {len(competitions)}")
        
        return 0
        
    except Exception as e:
        print(f"爬取出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
