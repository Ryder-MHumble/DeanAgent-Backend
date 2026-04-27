#!/usr/bin/env python3
"""
GitHub AI 领域贡献者爬虫
抓取 LLM/AI Agents 相关热门仓库的主要贡献者信息
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional

# GitHub API 配置
GITHUB_API = "https://api.github.com"
# 使用环境变量或直接设置 token（推荐使用环境变量）
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# 请求头
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "GitHub-AI-Crawler/1.0"
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# 搜索配置
SEARCH_TOPICS = [
    "llm",
    "machine-learning", 
    "deep-learning",
    "nlp",
    "reinforcement-learning",
    "autonomous-agents"
]
MIN_STARS = 1000
MIN_CONTRIBUTIONS = 50
MAX_REPOS = 30  # 最大仓库数（减少以适应未认证API限制）
RESULTS_PER_PAGE = 30

def rate_limit_wait():
    """处理 API 速率限制"""
    if GITHUB_TOKEN:
        # 认证请求: 5000次/小时
        time.sleep(0.1)
    else:
        # 未认证请求: 60次/小时
        time.sleep(1)

def github_request(url: str, params: Optional[dict] = None) -> Optional[dict]:
    """发送 GitHub API 请求"""
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        
        # 检查速率限制
        if response.status_code == 403:
            reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
            wait_seconds = max(reset_time - time.time(), 60)
            print(f"达到速率限制，等待 {wait_seconds:.0f} 秒...")
            time.sleep(wait_seconds)
            return github_request(url, params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"请求失败: {response.status_code} - {url}")
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def search_repositories(topic: str, page: int = 1) -> Optional[dict]:
    """搜索指定主题的仓库"""
    query = f"topic:{topic} stars:>{MIN_STARS} pushed:>2023-01-01"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": RESULTS_PER_PAGE,
        "page": page
    }
    url = f"{GITHUB_API}/search/repositories"
    return github_request(url, params)

def get_contributors(owner: str, repo: str) -> Optional[list]:
    """获取仓库贡献者列表"""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contributors"
    params = {"per_page": 100}  # 获取前100个贡献者
    return github_request(url, params)

def filter_major_contributors(contributors: list, min_contributions: int = MIN_CONTRIBUTIONS) -> list:
    """过滤主要贡献者"""
    return [
        {
            "login": c.get("login", ""),
            "contributions": c.get("contributions", 0),
            "avatar_url": c.get("avatar_url", ""),
            "html_url": c.get("html_url", "")
        }
        for c in contributors
        if c.get("contributions", 0) >= min_contributions
    ]

def crawl_github_repositories():
    """主爬虫函数"""
    results = {
        "source": "github",
        "crawl_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repositories": [],
        "stats": {
            "total_repos": 0,
            "total_contributors": 0,
            "topics_searched": []
        }
    }
    
    seen_repos = set()  # 去重
    total_contributors = 0
    
    for topic in SEARCH_TOPICS:
        print(f"\n搜索主题: {topic}")
        results["stats"]["topics_searched"].append(topic)
        
        page = 1
        topic_repos = 0
        
        while topic_repos < 10 and len(results["repositories"]) < MAX_REPOS:  # 每个主题最多10个仓库
            rate_limit_wait()
            
            search_result = search_repositories(topic, page)
            if not search_result or not search_result.get("items"):
                break
            
            for repo in search_result["items"]:
                full_name = repo.get("full_name", "")
                
                # 去重
                if full_name in seen_repos:
                    continue
                seen_repos.add(full_name)
                
                if len(results["repositories"]) >= MAX_REPOS:
                    break
                
                print(f"  处理仓库: {full_name} ({repo.get('stargazers_count', 0)} stars)")
                
                # 获取贡献者
                rate_limit_wait()
                contributors_data = get_contributors(repo["owner"]["login"], repo["name"])
                
                if contributors_data:
                    major_contributors = filter_major_contributors(contributors_data)
                    
                    if major_contributors:
                        repo_data = {
                            "full_name": full_name,
                            "stars": repo.get("stargazers_count", 0),
                            "language": repo.get("language", ""),
                            "topics": repo.get("topics", []),
                            "description": repo.get("description", ""),
                            "contributors": major_contributors
                        }
                        results["repositories"].append(repo_data)
                        total_contributors += len(major_contributors)
                        topic_repos += 1
                        print(f"    找到 {len(major_contributors)} 个主要贡献者")
            
            page += 1
            
            # 如果返回结果少于每页数量，说明没有更多了
            if len(search_result.get("items", [])) < RESULTS_PER_PAGE:
                break
        
        if len(results["repositories"]) >= MAX_REPOS:
            print(f"\n已达到最大仓库数 {MAX_REPOS}")
            break
    
    # 更新统计
    results["stats"]["total_repos"] = len(results["repositories"])
    results["stats"]["total_contributors"] = total_contributors
    
    return results

def main():
    print("=" * 60)
    print("GitHub AI 领域贡献者爬虫")
    print("=" * 60)
    print(f"最小 Stars: {MIN_STARS}")
    print(f"最小贡献数: {MIN_CONTRIBUTIONS}")
    print(f"最大仓库数: {MAX_REPOS}")
    print(f"搜索主题: {', '.join(SEARCH_TOPICS)}")
    print(f"GitHub Token: {'已配置' if GITHUB_TOKEN else '未配置 (速率限制较严格)'}")
    print("=" * 60)
    
    # 开始爬取
    results = crawl_github_repositories()
    
    # 保存结果
    output_path = "/data/dataset/excellent_20260425/github/results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("爬取完成!")
    print(f"总仓库数: {results['stats']['total_repos']}")
    print(f"总贡献者数: {results['stats']['total_contributors']}")
    print(f"结果保存至: {output_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
