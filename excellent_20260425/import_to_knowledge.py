#!/usr/bin/env python3
"""
将收集的学生信息写入知识库
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import uuid
import time

# 知识库配置
API_URL = "http://localhost:8080"
API_KEY = "6297e0cbe6784dfcbd78d58bb44c969d"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

BASE_DIR = Path("/data/dataset/excellent_20260425")

# 统计
stats = {
    "knowledge_created": 0,
    "statements_created": 0,
    "errors": []
}

def create_knowledge(name: str, content: dict, category: list, tags: list, meta: dict) -> dict:
    """创建知识条目"""
    data = {
        "name": name,
        "content": content,
        "category": category,
        "tags": tags,
        "meta": meta
    }
    
    try:
        resp = requests.post(f"{API_URL}/api/knowledge/create", headers=HEADERS, json=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        stats["knowledge_created"] += 1
        return result
    except Exception as e:
        stats["errors"].append(f"Knowledge error: {name} - {e}")
        return None

def create_statement(subject: str, predicate: str, obj: str, meta: dict = None) -> dict:
    """创建三元组"""
    data = {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "meta": meta or {}
    }
    
    try:
        resp = requests.post(f"{API_URL}/api/statement/create", headers=HEADERS, json=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        stats["statements_created"] += 1
        return result
    except Exception as e:
        stats["errors"].append(f"Statement error: {subject}-{predicate}-{obj} - {e}")
        return None

def process_olympiad():
    """处理奥赛数据"""
    print("处理奥赛数据...")
    
    with open(BASE_DIR / "olympiad/results.json") as f:
        data = json.load(f)
    
    for comp in data.get("competitions", []):
        comp_name = comp.get("name", "")
        comp_year = comp.get("year", "2024")
        
        for awardee in comp.get("awardees", []):
            name = awardee.get("name", "")
            school = awardee.get("school", "")
            award = awardee.get("award", "")
            
            if not name or name in ["待补充", "待确认"]:
                continue
            
            # 创建学生知识条目
            content = {
                "data": f"{name}，来自{school}，在{comp_name}中获得{award}。",
                "format": "markdown",
                "competition": comp_name,
                "award": award,
                "year": comp_year
            }
            
            meta = {
                "name": name,
                "school": school,
                "source": "olympiad",
                "competition": comp_name,
                "award": award,
                "year": comp_year,
                "category": ["student", "olympiad"],
                "allow-scope": ["*"]
            }
            
            result = create_knowledge(
                name=name,
                content=content,
                category=["student", "olympiad"],
                tags=["奥赛", comp_name[:20], school[:20]],
                meta=meta
            )
            
            if result:
                key = result.get("key", "")
                
                # 创建三元组
                if school:
                    create_statement(f"${key}", "就读于", school, {"source": "olympiad"})
                create_statement(f"${key}", "获得", award, {"competition": comp_name, "year": comp_year})
                create_statement(f"${key}", "参加", comp_name, {"year": comp_year})
            
            time.sleep(0.05)  # 避免请求过快

def process_academic():
    """处理学术论文作者数据"""
    print("处理学术论文作者数据...")
    
    with open(BASE_DIR / "academic_papers/results.json") as f:
        data = json.load(f)
    
    for author in data.get("authors", []):
        name = author.get("name", "")
        affiliations = author.get("affiliations", [])
        papers = author.get("papers", [])
        total_papers = author.get("total_papers", 0)
        total_citations = author.get("total_citations", 0)
        
        if not name:
            continue
        
        # 创建作者知识条目
        content = {
            "data": f"{name}，{'/'.join(affiliations[:2]) if affiliations else '未知机构'}，发表论文{total_papers}篇，被引用{total_citations}次。",
            "format": "markdown",
            "papers": papers[:5],
            "total_papers": total_papers,
            "total_citations": total_citations
        }
        
        meta = {
            "name": name,
            "affiliations": affiliations,
            "source": "academic_papers",
            "total_papers": total_papers,
            "total_citations": total_citations,
            "category": ["student", "researcher"],
            "allow-scope": ["*"]
        }
        
        result = create_knowledge(
            name=name,
            content=content,
            category=["student", "researcher", "academic"],
            tags=["学术论文", "AI/LLM"] + affiliations[:2],
            meta=meta
        )
        
        if result:
            key = result.get("key", "")
            
            # 创建三元组
            for aff in affiliations[:2]:
                create_statement(f"${key}", "所属机构", aff)
            
            for paper in papers[:3]:
                paper_title = paper.get("title", "")
                venue = paper.get("venue", "")
                if paper_title:
                    create_statement(f"${key}", "发表论文", paper_title[:50], {"venue": venue})
        
        time.sleep(0.05)

def process_kaggle():
    """处理 Kaggle 数据"""
    print("处理 Kaggle 数据...")
    
    with open(BASE_DIR / "kaggle/results.json") as f:
        data = json.load(f)
    
    for competitor in data.get("top_competitors", []):
        username = competitor.get("username", "")
        competitions = competitor.get("competitions", [])
        best_ranks = competitor.get("best_ranks", [])
        
        if not username:
            continue
        
        # 创建选手知识条目
        content = {
            "data": f"{username}，Kaggle竞赛选手，参加了{len(competitions)}个竞赛。",
            "format": "markdown",
            "competitions": competitions[:5],
            "best_ranks": best_ranks[:3]
        }
        
        meta = {
            "name": username,
            "source": "kaggle",
            "competitions": competitions,
            "category": ["student", "competitor", "kaggle"],
            "allow-scope": ["*"]
        }
        
        result = create_knowledge(
            name=username,
            content=content,
            category=["student", "competitor", "kaggle"],
            tags=["Kaggle", "竞赛"],
            meta=meta
        )
        
        if result:
            key = result.get("key", "")
            
            for comp in competitions[:3]:
                create_statement(f"${key}", "参加竞赛", comp)
        
        time.sleep(0.05)

def process_github():
    """处理 GitHub 贡献者数据"""
    print("处理 GitHub 贡献者数据...")
    
    with open(BASE_DIR / "github/results.json") as f:
        data = json.load(f)
    
    count = 0
    for repo in data.get("repositories", []):
        repo_name = repo.get("full_name", "")
        
        for contributor in repo.get("contributors", []):
            login = contributor.get("login", "")
            contributions = contributor.get("contributions", 0)
            
            if not login or contributions < 50:  # 只保留活跃贡献者
                continue
            
            # 创建贡献者知识条目
            content = {
                "data": f"{login}，GitHub开源贡献者，在{repo_name}中贡献{contributions}次。",
                "format": "markdown",
                "repo": repo_name,
                "contributions": contributions
            }
            
            meta = {
                "name": login,
                "source": "github",
                "repo": repo_name,
                "contributions": contributions,
                "category": ["student", "developer", "github"],
                "allow-scope": ["*"]
            }
            
            result = create_knowledge(
                name=login,
                content=content,
                category=["student", "developer", "github"],
                tags=["GitHub", "开源贡献", repo_name.split("/")[0]],
                meta=meta
            )
            
            if result:
                key = result.get("key", "")
                create_statement(f"${key}", "贡献于", repo_name, {"contributions": contributions})
            
            count += 1
            if count >= 100:  # 限制数量
                break
            
            time.sleep(0.05)
        
        if count >= 100:
            break

def process_ai4science():
    """处理 AI for Science 数据"""
    print("处理 AI for Science 数据...")
    
    with open(BASE_DIR / "ai4science/results.json") as f:
        data = json.load(f)
    
    for comp in data.get("competitions", []):
        comp_name = comp.get("name", "")
        comp_year = comp.get("year", "")
        
        for team in comp.get("teams", []):
            name = team.get("name", "")
            school = team.get("school", "")
            award = team.get("award", "")
            
            if not name:
                continue
            
            # 创建队伍知识条目
            content = {
                "data": f"{name}，{school}，在{comp_name}中获得{award}。",
                "format": "markdown",
                "competition": comp_name,
                "award": award
            }
            
            meta = {
                "name": name,
                "school": school,
                "source": "ai4science",
                "competition": comp_name,
                "award": award,
                "year": comp_year,
                "category": ["student", "competitor", "ai4science"],
                "allow-scope": ["*"]
            }
            
            result = create_knowledge(
                name=name,
                content=content,
                category=["student", "competitor", "ai4science"],
                tags=["AI4Science", comp_name[:15]],
                meta=meta
            )
            
            if result:
                key = result.get("key", "")
                
                if school:
                    create_statement(f"${key}", "来自", school)
                create_statement(f"${key}", "参加", comp_name, {"year": comp_year})
                if award:
                    create_statement(f"${key}", "获得", award)
            
            time.sleep(0.03)

def main():
    print("=" * 50)
    print("开始将学生信息写入知识库")
    print("=" * 50)
    
    # 处理各类数据
    process_olympiad()
    process_academic()
    process_kaggle()
    process_github()
    process_ai4science()
    
    # 输出统计
    print("\n" + "=" * 50)
    print("写入完成")
    print("=" * 50)
    print(f"知识条目创建: {stats['knowledge_created']}")
    print(f"三元组创建: {stats['statements_created']}")
    print(f"错误数: {len(stats['errors'])}")
    
    if stats['errors'][:5]:
        print("\n错误示例:")
        for err in stats['errors'][:5]:
            print(f"  - {err}")
    
    # 保存统计报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats
    }
    
    with open(BASE_DIR / "import_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n报告已保存: {BASE_DIR / 'import_report.json'}")

if __name__ == "__main__":
    main()
