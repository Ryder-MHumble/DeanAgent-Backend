#!/usr/bin/env python3
"""
规范化 institutions.json 的数据结构
1. 确保所有机构的字段完全一致
2. 为每个机构补充高校级和院系级的 org_name
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

AMINER_API_KEY = os.getenv("AMINER_API_KEY")
AMINER_PERSON_SEARCH_URL = "https://datacenter.aminer.cn/gateway/open_platform/api/person/search"
INSTITUTIONS_FILE = Path("data/scholars/institutions.json")

# 标准字段结构
STANDARD_UNIVERSITY_FIELDS = {
    "id": "",
    "name": "",
    "scholar_count": 0,
    "departments": [],
    "org_name": "",  # 高校级 org_name
    "details": {
        "category": None,
        "student_count_24": None,
        "student_count_25": None,
        "student_count_total": None,
        "mentor_count": None,
        "resident_leaders": [],
        "degree_committee": [],
        "teaching_committee": [],
        "mentor_info": None,
        "university_leaders": [],
        "notable_scholars": [],
        "key_departments": [],
        "joint_labs": [],
        "training_cooperation": [],
        "academic_cooperation": [],
        "talent_dual_appointment": [],
        "recruitment_events": [],
        "visit_exchanges": [],
        "priority": None,
        "cooperation_focus": []
    }
}

STANDARD_DEPARTMENT_FIELDS = {
    "id": "",
    "name": "",
    "scholar_count": 0,
    "org_name": "",  # 院系级 org_name
    "sources": []
}


def search_org_name(scholar_name: str, org_query: str, api_key: str) -> str | None:
    """通过学者搜索获取 org_name"""
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json;charset=utf-8",
    }

    payload = {
        "name": scholar_name,
        "org": org_query,
        "size": 5,
        "offset": 0,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                AMINER_PERSON_SEARCH_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                return None

            results = data.get("data", [])
            if not results:
                return None

            org_name = results[0].get("org", "")
            return org_name if org_name else None

    except Exception:
        return None


def normalize_university(univ: dict) -> dict:
    """规范化高校数据结构"""
    normalized = json.loads(json.dumps(STANDARD_UNIVERSITY_FIELDS))

    # 复制基本字段
    normalized["id"] = univ.get("id", "")
    normalized["name"] = univ.get("name", "")
    normalized["scholar_count"] = univ.get("scholar_count", 0)
    normalized["org_name"] = univ.get("org_name", "")

    # 复制 departments
    normalized["departments"] = []
    for dept in univ.get("departments", []):
        normalized["departments"].append(normalize_department(dept))

    # 复制 details
    if "details" in univ and univ["details"]:
        for key in normalized["details"].keys():
            if key in univ["details"]:
                normalized["details"][key] = univ["details"][key]

    return normalized


def normalize_department(dept: dict) -> dict:
    """规范化院系数据结构"""
    normalized = json.loads(json.dumps(STANDARD_DEPARTMENT_FIELDS))

    normalized["id"] = dept.get("id", "")
    normalized["name"] = dept.get("name", "")
    normalized["scholar_count"] = dept.get("scholar_count", 0)
    normalized["org_name"] = dept.get("org_name", "")
    normalized["sources"] = dept.get("sources", [])

    return normalized


def get_representative_scholar(univ: dict) -> str | None:
    """获取机构的代表性学者"""
    # 优先从 notable_scholars 获取
    notable_scholars = univ.get("details", {}).get("notable_scholars", [])
    if notable_scholars and isinstance(notable_scholars, list):
        for scholar in notable_scholars:
            if isinstance(scholar, dict) and scholar.get("name"):
                return scholar["name"]

    # 其次从 university_leaders 获取
    university_leaders = univ.get("details", {}).get("university_leaders", [])
    if university_leaders and isinstance(university_leaders, list):
        for leader in university_leaders:
            if isinstance(leader, dict) and leader.get("name"):
                return leader["name"]

    return None


def main():
    if not AMINER_API_KEY:
        print("错误: 未找到 AMINER_API_KEY 环境变量")
        sys.exit(1)

    if not INSTITUTIONS_FILE.exists():
        print(f"错误: {INSTITUTIONS_FILE} 不存在")
        sys.exit(1)

    # 读取数据
    with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    universities = data.get("universities", [])
    print(f"共 {len(universities)} 所高校需要处理\n")

    # 规范化并补充 org_name
    normalized_universities = []
    university_org_count = 0
    department_org_count = 0

    for i, univ in enumerate(universities, 1):
        univ_name = univ.get("name", "")
        univ_id = univ.get("id", "")

        print(f"[{i}/{len(universities)}] 处理 {univ_name} (ID: {univ_id})")

        # 规范化结构
        normalized_univ = normalize_university(univ)

        # 补充高校级 org_name
        if not normalized_univ["org_name"]:
            scholar_name = get_representative_scholar(univ)
            if scholar_name:
                print(f"  → 搜索高校级 org_name (学者: {scholar_name})")
                org_name = search_org_name(scholar_name, univ_name, AMINER_API_KEY)
                if org_name:
                    # 提取高校级别的 org_name（通常是最后一个部分）
                    parts = [p.strip() for p in org_name.split(';')]
                    # 选择最简洁的高校名称
                    university_org = None
                    for part in parts:
                        if univ_name[:2] in part or univ_id.upper() in part.upper():
                            university_org = part
                            break
                    if not university_org:
                        university_org = parts[-1]  # 默认使用最后一个

                    normalized_univ["org_name"] = university_org
                    university_org_count += 1
                    print(f"  ✓ 高校 org_name: {university_org}")
                else:
                    print(f"  ⚠ 未找到高校 org_name")

                time.sleep(0.5)
            else:
                print(f"  ⚠ 没有学者信息，无法获取 org_name")
        else:
            print(f"  ⊙ 已有高校 org_name: {normalized_univ['org_name']}")

        # 补充院系级 org_name
        for j, dept in enumerate(normalized_univ["departments"]):
            dept_name = dept["name"]
            dept_id = dept["id"]

            if not dept["org_name"]:
                # 尝试从 sources 中获取第一个学者
                sources = dept.get("sources", [])
                if sources and sources[0].get("scholar_count", 0) > 0:
                    # 构造院系查询（高校名 + 院系名）
                    dept_query = f"{dept_name}, {univ_name}"

                    # 使用高校的代表性学者来搜索院系
                    scholar_name = get_representative_scholar(univ)
                    if scholar_name:
                        print(f"    → 搜索院系 org_name: {dept_name}")
                        org_name = search_org_name(scholar_name, dept_query, AMINER_API_KEY)
                        if org_name:
                            # 提取院系级别的 org_name（通常是第一个部分）
                            parts = [p.strip() for p in org_name.split(';')]
                            department_org = parts[0]  # 使用第一个（最具体的）

                            dept["org_name"] = department_org
                            department_org_count += 1
                            print(f"    ✓ 院系 org_name: {department_org}")
                        else:
                            print(f"    ⚠ 未找到院系 org_name")

                        time.sleep(0.5)

        normalized_universities.append(normalized_univ)

    # 更新数据
    from datetime import datetime, timezone
    data["universities"] = normalized_universities
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    # 写回文件
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ 处理完成")
    print(f"  - 规范化高校: {len(normalized_universities)}")
    print(f"  - 补充高校 org_name: {university_org_count}")
    print(f"  - 补充院系 org_name: {department_org_count}")
    print(f"✓ 已更新 {INSTITUTIONS_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
