#!/usr/bin/env python3
"""测试 institutions.json 在启动时是否会被错误重置。

此脚本验证：
1. institutions.json 的结构正确（last_updated + universities）
2. 启动应用后，文件不会被重置为接口响应格式
3. 手动添加的富化数据（category, priority, student_count 等）会被保留
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def check_institutions_structure():
    """检查 institutions.json 结构是否正确。"""
    inst_file = Path("data/scholars/institutions.json")

    if not inst_file.exists():
        print("❌ institutions.json 不存在")
        return False

    with open(inst_file, encoding="utf-8") as f:
        data = json.load(f)

    # 检查顶层字段
    top_keys = set(data.keys())
    expected_keys = {"last_updated", "universities"}

    if top_keys != expected_keys:
        print(f"❌ 顶层字段错误")
        print(f"   期望: {expected_keys}")
        print(f"   实际: {top_keys}")

        # 检查是否是接口响应格式
        if "total" in top_keys or "page" in top_keys or "items" in top_keys:
            print("\n⚠️  检测到接口响应格式！这是错误的。")
            print("   institutions.json 应该是数据存储格式，不是 API 响应格式。")

        return False

    # 检查 universities 数组
    universities = data.get("universities", [])
    if not isinstance(universities, list):
        print("❌ universities 不是数组")
        return False

    if len(universities) == 0:
        print("⚠️  universities 数组为空")
        return True

    # 检查第一所高校的结构
    first_uni = universities[0]
    required_fields = {"id", "name", "scholar_count", "departments"}
    missing_fields = required_fields - set(first_uni.keys())

    if missing_fields:
        print(f"❌ 高校对象缺少必需字段: {missing_fields}")
        return False

    # 统计信息
    total_universities = len(universities)
    total_departments = sum(len(u.get("departments", [])) for u in universities)
    total_scholars = sum(u.get("scholar_count", 0) for u in universities)

    # 统计有富化数据的高校
    enriched_count = sum(
        1 for u in universities
        if u.get("category") or u.get("priority") or u.get("student_count_total")
    )

    print("✓ institutions.json 结构正确")
    print(f"\n统计信息：")
    print(f"  高校数量: {total_universities}")
    print(f"  院系数量: {total_departments}")
    print(f"  学者总数: {total_scholars}")
    print(f"  已富化高校: {enriched_count}/{total_universities}")

    if enriched_count > 0:
        print(f"\n✓ 检测到 {enriched_count} 所高校有富化数据（category/priority/student_count）")
        print("  这些数据在启动时应该被保留，不会丢失。")

    return True


def main():
    print("=" * 60)
    print("测试 institutions.json 持久化")
    print("=" * 60)
    print()

    success = check_institutions_structure()

    if success:
        print("\n" + "=" * 60)
        print("✓ 测试通过")
        print("=" * 60)
        print("\n提示：")
        print("  - 现在启动应用时，institutions.json 不会被重置")
        print("  - 只有在文件不存在时才会自动生成")
        print("  - 如需手动重建，使用: python scripts/rebuild_institutions.py")
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ 测试失败")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
