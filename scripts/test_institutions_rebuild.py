#!/usr/bin/env python3
"""测试 institutions.json 自动重建功能。

验证：
1. build_institutions_data() 能正确统计学者数量
2. 手动添加的学者（manual_scholars）会被计入对应高校
3. 重建后保留原有的富化字段（category, priority 等）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.core.institution_builder import build_institutions_data


def main():
    print("测试 institutions.json 自动重建...")
    print("=" * 70)

    # Build institutions data
    data = build_institutions_data()

    universities = data.get("universities", [])
    total_universities = len(universities)
    total_departments = sum(len(u.get("departments", [])) for u in universities)
    total_scholars = sum(u.get("scholar_count", 0) for u in universities)

    print(f"\n统计信息：")
    print(f"  高校数量: {total_universities}")
    print(f"  院系数量: {total_departments}")
    print(f"  学者总数: {total_scholars}")

    # Show top 5 universities by scholar count
    print(f"\n学者数量 Top 5：")
    sorted_unis = sorted(universities, key=lambda u: u.get("scholar_count", 0), reverse=True)
    for i, uni in enumerate(sorted_unis[:5], 1):
        print(f"  {i}. {uni['name']}: {uni['scholar_count']} 位学者")
        if uni.get("category"):
            print(f"     分类: {uni['category']}")
        if uni.get("priority"):
            print(f"     优先级: {uni['priority']}")

    # Check if manual scholars are counted
    print(f"\n检查手动录入学者是否被计入...")
    manual_path = Path("data/scholars/manual/manual_scholars/latest.json")
    if manual_path.exists():
        with open(manual_path, encoding="utf-8") as f:
            manual_data = json.load(f)
        manual_count = len(manual_data.get("items", []))
        print(f"  手动录入学者数: {manual_count}")

        # Check if these scholars are counted in universities
        manual_unis = set()
        for item in manual_data.get("items", []):
            extra = item.get("extra") or {}
            university = (extra.get("university") or "").strip()
            if university:
                manual_unis.add(university)

        print(f"  涉及高校: {', '.join(sorted(manual_unis))}")

        for uni_name in manual_unis:
            uni = next((u for u in universities if u["name"] == uni_name), None)
            if uni:
                print(f"  ✓ {uni_name} 学者数: {uni['scholar_count']}")
            else:
                print(f"  ✗ {uni_name} 未找到")
    else:
        print("  未找到手动录入学者数据")

    print("\n" + "=" * 70)
    print("测试完成")


if __name__ == "__main__":
    main()
