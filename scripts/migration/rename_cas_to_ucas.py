#!/usr/bin/env python3
"""Rename institution/scholar affiliation from 中国科学院 to 中国科学院大学.

Usage:
    python scripts/migration/rename_cas_to_ucas.py --dry-run
    python scripts/migration/rename_cas_to_ucas.py
"""

from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv

from app.db.client import get_client, init_client

OLD_NAME = "中国科学院"
NEW_NAME = "中国科学院大学"
ICT_ALIAS = "中国科学院计算技术研究所"
ICT_DEPARTMENT = "计算技术研究所"
DEFAULT_NEW_ORG_NAME = "University of Chinese Academy of Sciences"


async def run_migration(dry_run: bool = True, new_org_name: str = DEFAULT_NEW_ORG_NAME) -> None:
    """Apply the CAS -> UCAS rename migration in institutions + scholars tables."""
    load_dotenv(".env")
    await init_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    client = get_client()

    old_institutions_res = await (
        client.table("institutions")
        .select("id,name,org_name,entity_type,parent_id")
        .eq("name", OLD_NAME)
        .execute()
    )
    new_institutions_res = await (
        client.table("institutions")
        .select("id,name,org_name,entity_type,parent_id")
        .eq("name", NEW_NAME)
        .execute()
    )

    old_institutions = old_institutions_res.data or []
    new_institutions = new_institutions_res.data or []

    scholars_old_res = await (
        client.table("scholars")
        .select("id", count="exact")
        .eq("university", OLD_NAME)
        .limit(1)
        .execute()
    )
    scholars_new_res = await (
        client.table("scholars")
        .select("id", count="exact")
        .eq("university", NEW_NAME)
        .limit(1)
        .execute()
    )
    scholars_ict_alias_res = await (
        client.table("scholars")
        .select("id", count="exact")
        .eq("university", ICT_ALIAS)
        .limit(1)
        .execute()
    )

    old_count = scholars_old_res.count or 0
    new_count_before = scholars_new_res.count or 0
    ict_alias_count = scholars_ict_alias_res.count or 0

    print("=== 当前状态 ===")
    print(f"机构名 '{OLD_NAME}' 记录数: {len(old_institutions)}")
    print(f"机构名 '{NEW_NAME}' 记录数: {len(new_institutions)}")
    print(f"学者 university='{OLD_NAME}' 数量: {old_count}")
    print(f"学者 university='{ICT_ALIAS}' 数量: {ict_alias_count}")
    print(f"学者 university='{NEW_NAME}' 数量: {new_count_before}")

    if not old_institutions and old_count == 0 and ict_alias_count == 0:
        print("\n无需迁移：机构库和学者库都没有旧名称记录。")
        return

    if dry_run:
        print("\n[DRY-RUN] 预览完成，未写入数据库。")
        return

    # 1) Rename institutions (all rows matching old name)
    if old_institutions:
        await (
            client.table("institutions")
            .update({"name": NEW_NAME, "org_name": new_org_name})
            .eq("name", OLD_NAME)
            .execute()
        )

    # 2) Rename scholar affiliations
    if old_count > 0:
        await (
            client.table("scholars")
            .update({"university": NEW_NAME})
            .eq("university", OLD_NAME)
            .execute()
        )

    # 2b) Merge ICT alias scholars into UCAS + CAS ICT department
    if ict_alias_count > 0:
        await (
            client.table("scholars")
            .update({"university": NEW_NAME, "department": ICT_DEPARTMENT})
            .eq("university", ICT_ALIAS)
            .execute()
        )

    # 3) Verify
    verify_old_inst = (
        await client.table("institutions")
        .select("id", count="exact")
        .eq("name", OLD_NAME)
        .limit(1)
        .execute()
    )
    verify_new_inst = (
        await client.table("institutions")
        .select("id", count="exact")
        .eq("name", NEW_NAME)
        .limit(1)
        .execute()
    )
    verify_old_sch = (
        await client.table("scholars")
        .select("id", count="exact")
        .eq("university", OLD_NAME)
        .limit(1)
        .execute()
    )
    verify_new_sch = (
        await client.table("scholars")
        .select("id", count="exact")
        .eq("university", NEW_NAME)
        .limit(1)
        .execute()
    )
    verify_ict_alias = (
        await client.table("scholars")
        .select("id", count="exact")
        .eq("university", ICT_ALIAS)
        .limit(1)
        .execute()
    )

    print("\n=== 迁移完成 ===")
    print(f"机构名 '{OLD_NAME}' 剩余: {verify_old_inst.count or 0}")
    print(f"机构名 '{NEW_NAME}' 现有: {verify_new_inst.count or 0}")
    print(f"学者 university='{OLD_NAME}' 剩余: {verify_old_sch.count or 0}")
    print(f"学者 university='{ICT_ALIAS}' 剩余: {verify_ict_alias.count or 0}")
    print(f"学者 university='{NEW_NAME}' 现有: {verify_new_sch.count or 0}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rename CAS institution/scholar affiliation to UCAS"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write")
    parser.add_argument(
        "--new-org-name",
        default=DEFAULT_NEW_ORG_NAME,
        help="English org_name value for institutions table",
    )
    args = parser.parse_args()
    asyncio.run(run_migration(dry_run=args.dry_run, new_org_name=args.new_org_name))


if __name__ == "__main__":
    main()
