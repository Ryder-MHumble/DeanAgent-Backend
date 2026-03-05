#!/usr/bin/env python3
"""
补充 institutions.json 中缺失的 org_name 字段。
通过调用 AMiner API 查询机构信息。
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
        params = {
            "name": org_name,
            "token": AMINER_API_KEY,
        }
        response = await client.get(AMINER_API_URL, params=params, timeout=10)
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
    """补充 institutions.json 中的 org_name 字段。"""

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
    total_departments = 0
    updated_count = 0

    async with httpx.AsyncClient() as client:
        for uni in universities:
            uni_name = uni.get("name", "")
            departments = uni.get("departments", [])

            for dept in departments:
                total_departments += 1
                dept_name = dept.get("name", "")
                org_name = dept.get("org_name", "")

                # 如果 org_name 为空，则查询
                if not org_name or org_name.strip() == "":
                    full_name = f"{uni_name}{dept_name}"
                    print(f"\n🔍 查询: {full_name}")

                    org_info = await search_organization(client, full_name)

                    if org_info:
                        # 优先使用 name_en，其次使用 name_zh，最后使用 name
                        new_org_name = (
                            org_info.get("name_en") or
                            org_info.get("name_zh") or
                            org_info.get("name") or
                            ""
                        )

                        if new_org_name:
                            dept["org_name"] = new_org_name
                            updated_count += 1
                            print(f"  ✅ 更新: {new_org_name}")
                        else:
                            print(f"  ⚠️  API 返回的数据中没有 name 字段")
                    else:
                        print(f"  ⚠️  未找到匹配的机构")

                    # 避免 API 限流
                    await asyncio.sleep(0.5)
                else:
                    print(f"✓ {uni_name} - {dept_name}: {org_name}")

    # 保存更新后的数据
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"📊 统计:")
    print(f"  总部门数: {total_departments}")
    print(f"  更新数: {updated_count}")
    print(f"  文件已保存: {INSTITUTIONS_FILE}")


if __name__ == "__main__":
    asyncio.run(enrich_institutions())
