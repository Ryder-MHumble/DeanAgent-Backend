#!/usr/bin/env python3
"""
Academic Paper Author Crawler
抓取 AI/LLM/Agent 相关顶会论文的主要作者信息

使用的 API:
- Semantic Scholar API: 搜索论文和作者信息
- DBLP API: 查询作者发表记录
"""

import json
import time
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from collections import defaultdict

# 配置
OUTPUT_DIR = "/data/dataset/excellent_20260425/academic_papers"
OUTPUT_FILE = f"{OUTPUT_DIR}/results.json"

# 目标会议
TARGET_VENUES = [
    "ICML", "ICLR", "NeurIPS", "Neural Information Processing Systems",
    "AAAI", "ACL", "EMNLP", "CVPR", "ICCV", "NAACL", "EACL", "COLING",
    "AISTATS", "UAI", "IJCAI"
]

# 搜索关键词
KEYWORDS = [
    "large language model",
    "LLM",
    "GPT",
    "transformer",
    "agent",
    "autonomous agent",
    "foundation model",
    "language model"
]

# 速率限制 (秒)
RATE_LIMIT_DELAY = 2.0


class AuthorCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AcademicCrawler/1.0 (Research Purpose)"
        })
        self.authors_data: Dict[str, dict] = {}
        self.seen_papers: Set[str] = set()
        self.author_info_cache: Dict[str, dict] = {}
        
    def _rate_limit(self):
        """遵守速率限制"""
        time.sleep(RATE_LIMIT_DELAY)
    
    def _is_target_venue(self, venue: str) -> bool:
        """检查是否为目标会议"""
        if not venue:
            return False
        venue_upper = venue.upper()
        return any(v.upper() in venue_upper for v in TARGET_VENUES)
    
    def search_semantic_scholar(self, query: str, limit: int = 30) -> List[dict]:
        """使用 Semantic Scholar API 搜索论文"""
        print(f"[Semantic Scholar] 搜索: {query}")
        papers = []
        
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,venue,citationCount,publicationDate,openAccessPdf"
        }
        
        try:
            self._rate_limit()
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 429:
                print(f"[Semantic Scholar] 速率限制，等待...")
                time.sleep(30)
                return papers
            
            if response.status_code != 200:
                print(f"[Semantic Scholar] HTTP {response.status_code}")
                return papers
            
            data = response.json()
            
            if "data" in data:
                for paper in data["data"]:
                    paper_id = paper.get("paperId", "")
                    if paper_id in self.seen_papers:
                        continue
                    
                    self.seen_papers.add(paper_id)
                    papers.append({
                        "title": paper.get("title", ""),
                        "venue": paper.get("venue", ""),
                        "year": paper.get("year"),
                        "citations": paper.get("citationCount", 0),
                        "authors": paper.get("authors", []),
                        "paperId": paper_id
                    })
                        
            print(f"[Semantic Scholar] 找到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            print(f"[Semantic Scholar] 错误: {e}")
            return []
    
    def get_author_info_semantic_scholar(self, author_id: str) -> dict:
        """获取 Semantic Scholar 作者详细信息"""
        if author_id in self.author_info_cache:
            return self.author_info_cache[author_id]
            
        url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}"
        params = {
            "fields": "name,affiliations,citationCount,hIndex,paperCount"
        }
        
        try:
            self._rate_limit()
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 429:
                time.sleep(30)
                return {}
                
            if response.status_code != 200:
                return {}
            
            data = response.json()
            self.author_info_cache[author_id] = data
            return data
        except Exception as e:
            print(f"[Semantic Scholar Author] 错误: {e}")
            return {}
    
    def search_dblp(self, query: str) -> List[dict]:
        """使用 DBLP 搜索论文"""
        print(f"[DBLP] 搜索: {query}")
        papers = []
        
        url = "https://dblp.org/search/publ/api"
        params = {
            "q": query,
            "format": "json",
            "h": 30
        }
        
        try:
            self._rate_limit()
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if not isinstance(hits, list):
                hits = [hits] if hits else []
            
            for hit in hits:
                info = hit.get("info", {})
                venue = info.get("venue", "")
                
                paper_id = info.get("key", "")
                if paper_id in self.seen_papers:
                    continue
                
                self.seen_papers.add(paper_id)
                
                authors_info = info.get("authors", {}).get("author", [])
                if not isinstance(authors_info, list):
                    authors_info = [authors_info] if authors_info else []
                
                authors = []
                for a in authors_info:
                    if isinstance(a, dict):
                        authors.append({"name": a.get("text", "")})
                    elif isinstance(a, str):
                        authors.append({"name": a})
                
                papers.append({
                    "title": info.get("title", ""),
                    "venue": venue,
                    "year": int(info.get("year", 0) or 0),
                    "citations": 0,
                    "authors": authors,
                    "paperId": paper_id
                })
            
            print(f"[DBLP] 找到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            print(f"[DBLP] 错误: {e}")
            return []
    
    def process_paper(self, paper: dict):
        """处理单篇论文，提取作者信息"""
        for author in paper.get("authors", []):
            author_name = author.get("name", "") if isinstance(author, dict) else author
            if not author_name:
                continue
            
            author_key = author_name.lower().strip()
            
            if author_key not in self.authors_data:
                self.authors_data[author_key] = {
                    "name": author_name,
                    "affiliations": set(),
                    "papers": [],
                    "total_papers": 0,
                    "total_citations": 0,
                    "h_index": 0
                }
            
            # 添加论文
            paper_info = {
                "title": paper.get("title", ""),
                "venue": paper.get("venue", ""),
                "year": paper.get("year"),
                "citations": paper.get("citations", 0)
            }
            
            # 检查是否已存在相同论文
            exists = False
            for p in self.authors_data[author_key]["papers"]:
                if p["title"] == paper_info["title"]:
                    exists = True
                    break
            
            if not exists:
                self.authors_data[author_key]["papers"].append(paper_info)
            
            # 获取作者额外信息
            author_id = author.get("authorId", "") if isinstance(author, dict) else ""
            if author_id and len(self.authors_data[author_key]["affiliations"]) == 0:
                author_info = self.get_author_info_semantic_scholar(author_id)
                if author_info:
                    if author_info.get("affiliations"):
                        for aff in author_info.get("affiliations", []):
                            self.authors_data[author_key]["affiliations"].add(aff)
                    if author_info.get("hIndex"):
                        self.authors_data[author_key]["h_index"] = max(
                            self.authors_data[author_key]["h_index"],
                            author_info.get("hIndex", 0)
                        )
    
    def aggregate_author_stats(self):
        """汇总作者统计信息"""
        for author_key, data in self.authors_data.items():
            # 计算总论文数
            data["total_papers"] = len(data["papers"])
            
            # 计算总引用数
            data["total_citations"] = sum(
                p.get("citations", 0) for p in data["papers"]
            )
            
            # 计算 H-index (基于相关论文)
            if data["h_index"] == 0:
                citations_list = sorted(
                    [p.get("citations", 0) for p in data["papers"]],
                    reverse=True
                )
                h_index = 0
                for i, c in enumerate(citations_list, 1):
                    if c >= i:
                        h_index = i
                    else:
                        break
                data["h_index"] = h_index
            
            # 转换 affiliations 为列表
            data["affiliations"] = list(data["affiliations"])
    
    def crawl(self):
        """执行爬取任务"""
        print("=" * 60)
        print("开始爬取学术论文作者信息")
        print("=" * 60)
        
        all_papers = []
        
        # 1. Semantic Scholar 关键词搜索
        print("\n[阶段 1] Semantic Scholar 关键词搜索")
        for keyword in KEYWORDS[:5]:
            papers = self.search_semantic_scholar(keyword, limit=30)
            all_papers.extend(papers)
            time.sleep(3)
        
        # 2. DBLP 搜索
        print("\n[阶段 2] DBLP 搜索")
        for keyword in KEYWORDS[:3]:
            papers = self.search_dblp(keyword)
            all_papers.extend(papers)
            time.sleep(2)
        
        # 3. 处理论文数据
        print("\n[阶段 3] 处理论文数据")
        for paper in all_papers:
            self.process_paper(paper)
        
        # 4. 汇总统计
        print("\n[阶段 4] 汇总统计")
        self.aggregate_author_stats()
        
        # 5. 生成结果
        print("\n[阶段 5] 生成结果文件")
        result = {
            "source": "academic_papers",
            "crawl_time": datetime.now(timezone.utc).isoformat(),
            "total_authors": len(self.authors_data),
            "total_papers": len(self.seen_papers),
            "authors": list(self.authors_data.values())
        }
        
        # 按总引用数排序
        result["authors"].sort(key=lambda x: x["total_citations"], reverse=True)
        
        # 只保留 top 作者
        top_count = min(200, len(result["authors"]))
        result["authors"] = result["authors"][:top_count]
        result["top_authors_count"] = len(result["authors"])
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n爬取完成！")
        print(f"- 总作者数: {result['total_authors']}")
        print(f"- 总论文数: {result['total_papers']}")
        print(f"- Top 作者数: {result['top_authors_count']}")
        print(f"- 输出文件: {OUTPUT_FILE}")
        
        return result


def main():
    crawler = AuthorCrawler()
    crawler.crawl()


if __name__ == "__main__":
    main()
