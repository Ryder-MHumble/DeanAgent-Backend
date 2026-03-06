#!/usr/bin/env python3
"""手动重建 institutions.json — 仅在需要时使用（如添加新学者信源后）。

警告：此脚本会重新生成 institutions.json，只保留从 YAML 配置和学者数据中提取的信息。
     手动添加的富化数据（category, priority, student_count 等）会被保留，
     但如果你有其他自定义字段，请先备份。

用法：
    python scripts/rebuild_institutions.py              # 重建并保存
    python scripts/rebuild_institutions.py --dry-run    # 仅预览，不保存
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.core.institution_builder import build_institutions_data, save_institutions_data


def main():
    parser = argparse.ArgumentParser(description="重建 institutions.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不保存文件",
    )
    args = parser.parse_args()

    print("正在从 YAML 配置和学者数据重建 institutions.json...")
    data = build_institutions_data()

    universities = data.get("universities", [])
    total_universities = len(universities)
    total_departments = sum(len(u.get("departments", [])) for u in universities)
    total_scholars = sum(u.get("scholar_count", 0) for u in universities)

    print(f"\n统计信息：")
    print(f"  高校数量: {total_universities}")
    print(f"  院系数量: {total_departments}")
    print(f"  学者总数: {total_scholars}")

    if args.dry_run:
        print("\n[DRY RUN] 预览前 3 所高校：")
        for uni in universities[:3]:
            print(f"\n  - {uni['name']} ({uni['id']})")
            print(f"    学者数: {uni['scholar_count']}")
            print(f"    院系数: {len(uni.get('departments', []))}")
            if uni.get("category"):
                print(f"    分类: {uni['category']}")
            if uni.get("priority"):
                print(f"    优先级: {uni['priority']}")
        print("\n未保存文件（使用 --dry-run）")
    else:
        output_path = save_institutions_data(data)
        print(f"\n✓ 已保存到: {output_path}")


if __name__ == "__main__":
    main()
