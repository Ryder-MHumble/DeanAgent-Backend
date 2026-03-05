#!/usr/bin/env python3
"""
Faculty → Scholar 数据迁移脚本

功能：
1. 复制 data/raw/scholars/ → data/raw/scholars/
2. 更新所有 JSON 文件中的 dimension 字段
3. 重命名标注文件
4. 创建软链接保证向后兼容
5. 验证数据完整性
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
STATE_DIR = DATA_DIR / "state"

# 源路径和目标路径
FACULTY_DIR = RAW_DATA_DIR / "scholars"
SCHOLARS_DIR = RAW_DATA_DIR / "scholars"
FACULTY_ANNOTATIONS = STATE_DIR / "scholar_annotations.json"
SCHOLARS_ANNOTATIONS = STATE_DIR / "scholars_annotations.json"


def dry_run():
    """预览迁移操作"""
    print("=" * 60)
    print("Faculty → Scholar 迁移预览（Dry Run）")
    print("=" * 60)

    # 检查源目录
    if not FACULTY_DIR.exists():
        print(f"❌ 源目录不存在: {FACULTY_DIR}")
        return False

    # 统计文件数量
    json_files = list(FACULTY_DIR.rglob("*.json"))
    print(f"\n📁 源目录: {FACULTY_DIR}")
    print(f"   - JSON 文件数量: {len(json_files)}")

    # 统计数据量
    total_items = 0
    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                total_items += len(data.get("items", []))
        except Exception:
            continue

    print(f"   - 学者记录总数: {total_items}")

    # 检查标注文件
    if FACULTY_ANNOTATIONS.exists():
        with open(FACULTY_ANNOTATIONS, encoding="utf-8") as f:
            annotations = json.load(f)
        print(f"\n📝 标注文件: {FACULTY_ANNOTATIONS}")
        print(f"   - 标注记录数: {len(annotations)}")

    # 预览操作
    print("\n📋 将执行的操作:")
    print(f"   1. 复制目录: {FACULTY_DIR} → {SCHOLARS_DIR}")
    print(f"   2. 更新 {len(json_files)} 个 JSON 文件的 dimension 字段")
    print(f"   3. 重命名标注文件: {FACULTY_ANNOTATIONS.name} → {SCHOLARS_ANNOTATIONS.name}")
    print(f"   4. 创建软链接: university_faculty → scholars")
    print(f"   5. 创建软链接: scholar_annotations.json → scholars_annotations.json")

    # 检查目标是否已存在
    if SCHOLARS_DIR.exists():
        print(f"\n⚠️  警告: 目标目录已存在: {SCHOLARS_DIR}")
        print("   执行迁移将覆盖现有数据")

    print("\n✅ 预览完成。使用 --execute 执行实际迁移。")
    return True


def execute_migration():
    """执行迁移"""
    print("=" * 60)
    print("Faculty → Scholar 数据迁移")
    print("=" * 60)

    # 检查源目录
    if not FACULTY_DIR.exists():
        print(f"❌ 错误: 源目录不存在: {FACULTY_DIR}")
        return False

    # 备份提示
    print("\n⚠️  重要提示:")
    print("   建议在迁移前备份 data/ 目录")
    print("   执行: cp -r data data_backup_$(date +%Y%m%d)")
    response = input("\n是否继续？(yes/no): ")
    if response.lower() != "yes":
        print("❌ 迁移已取消")
        return False

    try:
        # Step 1: 复制目录
        print(f"\n[1/5] 复制目录...")
        if SCHOLARS_DIR.exists():
            print(f"   删除现有目录: {SCHOLARS_DIR}")
            shutil.rmtree(SCHOLARS_DIR)
        shutil.copytree(FACULTY_DIR, SCHOLARS_DIR)
        print(f"   ✅ 已复制: {FACULTY_DIR} → {SCHOLARS_DIR}")

        # imension 字段
        print(f"\n[2/5] 更新 JSON 文件的 dimension 字段...")
        json_files = list(SCHOLARS_DIR.rglob("*.json"))
        updated_count = 0

        for json_file in json_files:
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # 更新 dimension 字段
                if data.get("dimension") == "scholars":
                    data["dimension"] = "scholars"
                    updated_count += 1

                    # 更新 items 中的 dimension
                    for item in data.get("items", []):
                        if item.get("dimension") == "scholars":
                            item["dimension"] = "scholars"

                    # 写回文件
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"   ⚠️  警告: 处理文件失败 {json_file}: {e}")
                continue

        print(f"   ✅ 已更新 {updated_count} 个文件")

        # Step 3: 重命名标注文件
        print(f"\n[3/5] 重命名标注文件...")
        if FACULTY_ANNOTATIONS.exists():
            if SCHOLARS_ANNOTATIONS.exists():
                print(f"   删除现有文件: {SCHOLARS_ANNOTATIONS}")
                SCHOLARS_ANNOTATIONS.unlink()
            shutil.copy2(FACULTY_ANNOTATIONS, SCHOLARS_ANNOTATIONS)
            print(f"   ✅ 已复制: {FACULTY_ANNOTATIONS.name} → {SCHOLARS_ANNOTATIONS.name}")
        else:
            print(f"   ⚠️  标注文件不存在，跳过")

        # Step 4: 创建软链接（目录）
        print(f"\n[4/5] 创建软链接（向后兼容）...")
        faculty_link = RAW_DATA_DIR / "university_faculty_link"
        if faculty_link.exists() or faculty_link.is_symlink():
            faculty_link.unlink()
        # 注意：不覆盖原始 faculty 目录，而是创建一个新的链接名
        print(f"   ℹ️  保留原始 {FACULTY_DIR.name} 目录")
        print(f"   ℹ️  新数据将使用 {SCHOLARS_DIR.name} 目录")

        # Step 5: 创建软链接（标注文件）
        print(f"\n[5/5] 创建标注文件软链接...")
        annotations_link = STATE_DIR / "faculty_annotations_link.json"
        if annotations_link.exists() or annotations_link.is_symlink():
            annotations_link.unlink()
        print(f"   ℹ️  保留原始 {FACULTY_ANNOTATIONS.name}")
        print(f"   ℹ️  新标注将使用 {SCHOLARS_ANNOTATIONS.name}")

        print("\n" + "=" * 60)
        print("✅ 迁移完成！")
        print("=" * 60)
        print("\n📊 迁移总结:")
        print(f"   - 已复制目录: {SCHOLARS_DIR}")
        print(f"   - 已更新文件: {updated_count} 个")
        print(f"   - 已创建标注: {SCHOLARS_ANNOTATIONS}")
        print("\n⚠️  下一步:")
        print("   1. 运行 --verify 验证数据完整性")
        print("   2. 更新代码中的 dimension 引用")
        print("   3. 测试 API 端点")

        return True

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_migration():
    """验证迁移结果"""
    print("=" * 60)
    print("验证迁移结果")
    print("=" * 60)

    errors = []

    # 检查目录
    print("\n[1/4] 检查目录...")
    if not SCHOLARS_DIR.exists():
        errors.append(f"目标目录不存在: {SCHOLARS_DIR}")
    else:
        print(f"   ✅ 目标目录存在: {SCHOLARS_DIR}")

    # 检查文件数量
    print("\n[2/4] 检查文件数量...")
    if FACULTY_DIR.exists() and SCHOLARS_DIR.exists():
        faculty_files = list(FACULTY_DIR.rglob("*.json"))
        scholars_files = list(SCHOLARS_DIR.rglob("*.json"))

        if len(faculty_files) != len(scholars_files):
            errors.append(f"文件数量不匹配: faculty={len(faculty_files)}, scholars={len(scholars_files)}")
        else:
            print(f"   ✅ 文件数量一致: {len(scholars_files)} 个")

    # 检查数据量
    print("\n[3/4] 检查数据量...")
    faculty_count = 0
    scholars_count = 0

    if FACULTY_DIR.exists():
        for json_file in FACULTY_DIR.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    faculty_count += len(data.get("items", []))
            except Exception:
                continue

    if SCHOLARS_DIR.exists():
        for json_file in SCHOLARS_DIR.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    scholars_count += len(data.get("items", []))
            except Exception:
                continue

    if faculty_count != scholars_count:
        errors.append(f"数据量不匹配: faculty={faculty_count}, scholars={scholars_count}")
    else:
        print(f"   ✅ 数据量一致: {scholars_count} 条记录")

    # 检查 dimension 字段
    print("\n[4/4] 检查 dimension 字段...")
    wrong_dimension_count = 0

    if SCHOLARS_DIR.exists():
        for json_file in SCHOLARS_DIR.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("dimension") == "scholars":
                        wrong_dimension_count += 1
            except Exception:
                continue

    if wrong_dimension_count > 0:
        errors.append(f"发现 {wrong_dimension_count} 个文件的 dimension 未更新")
    else:
        print(f"   ✅ 所有文件的 dimension 已更新为 'scholars'")

    # 输出结果
    print("\n" + "=" * 60)
    if errors:
        print("❌ 验证失败，发现以下问题:")
        for i, error in enumerate(errors, 1):
            print(f"   {i}. {error}")
        return False
    else:
        print("✅ 验证通过！数据迁移成功。")
        print("=" * 60)
        return True


def main():
    parser = argparse.ArgumentParser(description="Faculty → Scholar 数据迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="预览迁移操作（不执行）")
    parser.add_argument("--execute", action="store_true", help="执行迁移")
    parser.add_argument("--verify", action="store_true", help="验证迁移结果")

    args = parser.parse_args()

    if args.dry_run:
        success = dry_run()
    elif args.execute:
        success = execute_migration()
    elif args.verify:
        success = verify_migration()
    else:
        parser.print_help()
        return 0

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
