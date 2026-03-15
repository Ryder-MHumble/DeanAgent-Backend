#!/usr/bin/env python3
"""通用数据库 Schema 迁移验证工具.

用于验证数据库表结构变更后的数据完整性和一致性。

Usage:
    python scripts/verify_db_migration.py <table_name> [--check-fields field1,field2,...]

Examples:
    # 验证 institutions 表的新字段
    python scripts/verify_db_migration.py institutions --check-fields entity_type,region,org_type

    # 验证 articles 表
    python scripts/verify_db_migration.py articles
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def verify_migration(
    table_name: str,
    check_fields: list[str] | None = None,
    consistency_checks: dict[str, Any] | None = None,
) -> bool:
    """验证数据库迁移结果.

    Args:
        table_name: 表名
        check_fields: 需要检查的新字段列表
        consistency_checks: 自定义一致性检查函数

    Returns:
        True if all checks pass, False otherwise
    """
    from app.db.client import get_client, init_client

    # 从环境变量读取配置
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("✗ 缺少环境变量: SUPABASE_URL 或 SUPABASE_KEY")
        print("  请确保 .env 文件存在并包含这两个变量")
        return False

    try:
        await init_client(url, key)
        client = get_client()
    except Exception as exc:
        print(f"✗ 数据库连接失败: {exc}")
        return False

    print("=" * 80)
    print(f"{table_name} 表迁移验证")
    print("=" * 80)

    all_passed = True

    # 1. 检查新字段是否存在
    if check_fields:
        print(f"\n[1/5] 检查新字段 ({', '.join(check_fields)})...")
        try:
            select_fields = ",".join(check_fields)
            res = await client.table(table_name).select(select_fields).limit(1).execute()
            print("✓ 新字段已添加")
        except Exception as exc:
            print(f"✗ 新字段缺失: {exc}")
            all_passed = False
            return all_passed

    # 2. 检查是否有未迁移的记录
    if check_fields:
        print("\n[2/5] 检查未迁移记录...")
        try:
            # 检查第一个字段是否为 NULL
            res = await client.table(table_name).select("id,name," + check_fields[0]).is_(check_fields[0], "null").execute()
            unmigrated = res.data or []
            if unmigrated:
                print(f"✗ 发现 {len(unmigrated)} 条未迁移记录:")
                for row in unmigrated[:5]:
                    print(f"  - {row.get('id')}: {row.get('name')}")
                all_passed = False
            else:
                print("✓ 所有记录已迁移")
        except Exception as exc:
            print(f"⚠ 无法检查未迁移记录: {exc}")

    # 3. 统计迁移结果
    print("\n[3/5] 统计迁移结果...")
    try:
        res = await client.table(table_name).select("*").execute()
        all_rows = res.data or []
        print(f"总记录数: {len(all_rows)}")

        if check_fields and all_rows:
            # 统计各字段的分布
            for field in check_fields:
                stats: dict[str, int] = {}
                for row in all_rows:
                    value = row.get(field) or "NULL"
                    stats[str(value)] = stats.get(str(value), 0) + 1

                print(f"\n按 {field} 分布:")
                for k, v in sorted(stats.items(), key=lambda x: -x[1])[:10]:
                    print(f"  {k}: {v}")
    except Exception as exc:
        print(f"✗ 统计失败: {exc}")
        all_passed = False

    # 4. 数据一致性检查
    if consistency_checks:
        print("\n[4/5] 检查数据一致性...")
        try:
            res = await client.table(table_name).select("*").execute()
            all_rows = res.data or []

            issues = []
            for row in all_rows:
                for check_name, check_func in consistency_checks.items():
                    if not check_func(row):
                        issues.append(f"{row.get('id')}: {check_name}")

            if issues:
                print(f"✗ 发现 {len(issues)} 个一致性问题:")
                for issue in issues[:10]:
                    print(f"  - {issue}")
                all_passed = False
            else:
                print("✓ 数据一致性检查通过")
        except Exception as exc:
            print(f"✗ 一致性检查失败: {exc}")
            all_passed = False

    # 5. 测试查询
    print("\n[5/5] 测试查询...")
    try:
        # 简单查询测试
        res = await client.table(table_name).select("id,name").limit(5).execute()
        print(f"✓ 查询成功: 返回 {len(res.data or [])} 条记录")
    except Exception as exc:
        print(f"✗ 查询失败: {exc}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✓ 验证完成：所有检查通过")
    else:
        print("✗ 验证完成：部分检查失败")
    print("=" * 80)

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="验证数据库 Schema 迁移结果")
    parser.add_argument("table", help="表名")
    parser.add_argument(
        "--check-fields",
        help="需要检查的新字段（逗号分隔）",
        default="",
    )
    parser.add_argument(
        "--consistency-checks",
        help="一致性检查配置文件路径（Python 文件）",
        default="",
    )

    args = parser.parse_args()

    check_fields = [f.strip() for f in args.check_fields.split(",") if f.strip()]

    # 加载一致性检查（如果提供）
    consistency_checks = None
    if args.consistency_checks and Path(args.consistency_checks).exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("checks", args.consistency_checks)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            consistency_checks = getattr(module, "CONSISTENCY_CHECKS", None)

    success = asyncio.run(verify_migration(
        args.table,
        check_fields=check_fields or None,
        consistency_checks=consistency_checks,
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
