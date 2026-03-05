#!/usr/bin/env python3
"""
通过 AMiner 学者搜索 API 获取机构的 org_name
策略：搜索每个机构的知名学者，从返回结果中提取 org 字段作为 org_name
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

AMINER_API_KEY = os.getenv("AMINER_API_KEY")
AMINER_PERSON_SEARCH_URL = "https://datacenter.aminer.cn/gateway/open_platform/api/person/search"
INSTITUTIONS_FILE = Path("data/scholars/institutions.json")

# 每个机构的代表性学者（用于搜索）
REPRESENTATIVE_SCHOLARS = {
    "tsinghua": "姚期智",
    "pku": "鄂维南",
    "sjtu": "严骏驰",
    "ruc": "文继荣",
    "nju": "周志华",
    "fudan": "杨珉",
    "zju": "陈纯",
    "ustc": "潘建伟",
    "cas": "张钹",
}


def search_scholar_to_get_org(scholar_name: str, univ_name: str, api_key: str) -> str | None:
    """通过搜索学者来获取机构的 org_name.

    Args:
        scholar_name: 学者姓名
        univ_name: 机构名称（用于验证）
        api_key: AMiner API Key

    Returns:
        机构的 org_name，如果未找到则返回 None
    """
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json;charset=utf-8",
    }

    payload = {
        "name": scholar_name,
        "org": univ_name,
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
                print(f"  ⚠ API 返回失败: {data.get('msg', 'Unknown error')}")
                return None

            results = data.get("data", [])
            if not results:
                print(f"  ⚠ 未找到学者 {scholar_name}")
                return None

            # 从第一个结果中提取 org
            first_result = results[0]
            org_name = first_result.get("org", "")

            if org_name:
                print(f"  ✓ 找到 org_name: {org_name}")
                return org_name
            else:
                print(f"  ⚠ 学者结果中没有 org 字段")
                return None

    except httpx.HTTPStatusError as e:
        print(f"  ✗ HTTP 错误: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"  ✗ 请求错误: {e}")
        return None
    except Exception as e:
        print(f"  ✗ 未知错误: {e}")
        return None


def enrich_institutions_with_org_name():
    """为所有机构补充 org_name 字段."""
    if not AMINER_API_KEY:
        print("错误: 未找到 AMINER_API_KEY 环境变量")
        sys.exit(1)

    if not INSTITUTIONS_FILE.exists():
        print(f"错误: {INSTITUTIONS_FILE} 不存在")
        sys.exit(1)

    # 读取 institutions.json
    with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    universities = data.get("universities", [])
    print(f"共 {len(universities)} 所高校需要处理\n")

    enriched_count = 0
    failed_count = 0

    for i, univ in enumerate(universities, 1):
        univ_name = univ.get("name", "")
        univ_id = univ.get("id", "")

        print(f"[{i}/{len(universities)}] 处理 {univ_name} (ID: {univ_id})")

        # 检查是否已有 org_name
        if "org_name" in univ and univ["org_name"]:
            print(f"  ⊙ 已有 org_name: {univ['org_name']}")
            enriched_count += 1
            continue

        # 获取代表性学者
        scholar_name = REPRESENTATIVE_SCHOLARS.get(univ_id)
        if not scholar_name:
            # 如果没有预设学者，尝试从 notable_scholars 中获取
            notable_scholars = univ.get("details", {}).get("notable_scholars", [])
            if notable_scholars:
                scholar_name = notable_scholars[0].get("name")
                print(f"  → 使用机构学者: {scholar_name}")
            else:
                print(f"  ⚠ 没有可用的学者信息，跳过")
                failed_count += 1
                continue

        # 通过学者搜索获取 org_name
        org_name = search_scholar_to_get_org(scholar_name, univ_name, AMINER_API_KEY)

        if org_name:
            univ["org_name"] = org_name
            enriched_count += 1
        else:
            failed_count += 1

        # 避免 API 限流
        time.sleep(0.5)

    # 更新时间戳
    from datetime import datetime, timezone
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    # 写回文件
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ 处理完成")
    print(f"  - 成功补充: {enriched_count}/{len(universities)}")
    print(f"  - 失败: {failed_count}/{len(universities)}")
    print(f"✓ 已更新 {INSTITUTIONS_FILE}")
    print(f"{'='*60}")


def main():
    try:
        enrich_institutions_with_org_name()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
