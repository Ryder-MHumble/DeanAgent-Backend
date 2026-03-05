#!/usr/bin/env python3
"""
从 AMiner API 查询高校和院系的真实 org_name。

功能：
1. 为每个高校查询 org_name（如"上海交通大学" → "Shanghai Jiao Tong University"）
2. 为每个院系查询 org_name（如"上海交通大学人工智能研究院" → "Shanghai Jiao Tong University AI Institute"）

API 调用：
- POST https://datacenter.aminer.cn/gateway/open_platform/api/organization/search
- Authorization: Bearer token (from .env AMINER_API_KEY)
- Body: {"orgs": ["机构名称"]}

使用方法：
    python scripts/enrich_institutions_from_aminer.py
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

AMINER_API_KEY = os.getenv("AMINER_API_KEY")
AMINER_API_URL = "https://datacenter.aminer.cn/gateway/open_platform/api/organization/search"

DATA_DIR = Path(__file__).parent.parent / "data"
INSTITUTIONS_FILE = DATA_DIR / "institutions.json"


async def search_organization(client: httpx.AsyncClient, org_name: str) -> Optional[dict]:
    """
    调用 AMiner API 查询机构信息。

    Args:
        client: httpx 异步客户端
        org_name: 机构名称

    Returns:
        机构信息字典，如果查询失败返回 None
    """
    try:
        headers = {
            "Authorization": AMINER_API_KEY,
            "Content-Type": "application/json;charset=utf-8",
        }
        payload = {
            "orgs": [org_name]
        }
        response = await client.post(AMINER_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("success") and data.get("data"):
            orgs = data["data"]
            if orgs and len(orgs) > 0:
                # 返回第一个匹配结果
                return orgs[0]
        return None
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        return None


async def enrich_institutions():
    """从 AMiner API 补充 institutions.json 中的 org_name 字段（高校 + 院系）。"""

    if not AMINER_API_KEY:
        print("❌ 错误: 未设置 AMINER_API_KEY")
        return

    # 读取 institutions.json
    if not INSTITUTIONS_FILE.exists():
        print(f"❌ 文件不存在: {INSTITUTIONS_FILE}")
        return

    with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    universities = data.get("universities", [])
    total_unis = len(universities)
    total_depts = 0
    uni_updated = 0
    uni_failed = 0
    dept_updated = 0
    dept_failed = 0

    async with httpx.AsyncClient() as client:
        for uni in universities:
            uni_name = uni.get("name", "")
            print(f"\n{'='*60}")
            print(f"🏫 处理高校: {uni_name}")

            # 1. 查询高校的 org_name
            uni_org_info = await search_organization(client, uni_name)
            uni_org_name = ""
            if uni_org_info:
                uni_org_name = uni_org_info.get("org_name", "")
                if uni_org_name:
                    uni["org_name"] = uni_org_name
                    uni_updated += 1
                    print(f"  ✅ 高校 org_name: {uni_org_name}")
                else:
                    uni_failed += 1
                    print(f"  ⚠️  API 返回的数据中没有 org_name 字段")
            else:
                uni_failed += 1
                print(f"  ⚠️  未找到高校的 org_name")

            # 避免 API 限流
            await asyncio.sleep(0.5)

            # 2. 查询院系的 org_name
            departments = uni.get("departments", [])
            for dept in departments:
                total_depts += 1
                dept_name = dept.get("name", "")

                # 用"高校名 + 院系名"查询
                search_name = f"{uni_name}{dept_name}"
                print(f"  🔍 查询院系: {search_name}")

                org_info = await search_organization(client, search_name)

                if org_info:
                    new_org_name = org_info.get("org_name", "")

                    if new_org_name:
                        dept["org_name"] = new_org_name
                        dept_updated += 1
                        print(f"    ✅ 院系 org_name: {new_org_name}")
                    else:
                        dept_failed += 1
                        print(f"    ⚠️  API 返回的数据中没有 org_name 字段")
                else:
                    dept_failed += 1
                    print(f"    ⚠️  未找到匹配的机构")

                # 避免 API 限流
                await asyncio.sleep(0.5)

    # 更新 last_updated 时间戳
    from datetime import datetime, timezone
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    # 保存更新后的数据
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"📊 统计:")
    print(f"  总高校数: {total_unis}")
    print(f"    ✅ 成功更新: {uni_updated}")
    print(f"    ❌ 查询失败: {uni_failed}")
    print(f"  总院系数: {total_depts}")
    print(f"    ✅ 成功更新: {dept_updated}")
    print(f"    ❌ 查询失败: {dept_failed}")
    print(f"  文件已保存: {INSTITUTIONS_FILE}")


if __name__ == "__main__":
    asyncio.run(enrich_institutions())
