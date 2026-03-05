#!/usr/bin/env python3
"""数据结构迁移脚本：university_faculty → scholars"""
import json
import shutil
from pathlib import Path


def migrate_data_directories():
    """迁移数据目录结构"""
    base_dir = Path(__file__).parent.parent

    # 1. 迁移主数据目录
    old_dir = base_dir / "data" / "raw" / "scholars"
    new_dir = base_dir / "data" / "scholars"

    if old_dir.exists():
        print(f"Migrating {old_dir} → {new_dir}")
        if new_dir.exists():
            print(f"  Warning: {new_dir} already exists, skipping...")
        else:
            shutil.move(str(old_dir), str(new_dir))
            print(f"  ✓ Migrated successfully")
    else:
        print(f"  ✗ {old_dir} not found")

    # 2. 迁移 annotations 文件
    old_anno = base_dir / "data" / "state" / "scholar_annotations.json"
    new_anno = base_dir / "data" / "state" / "scholar_annotations.json"

    if old_anno.exists():
        print(f"\nMigrating {old_anno.name} → {new_anno.name}")
        if new_anno.exists():
            print(f"  Warning: {new_anno} already exists, skipping...")
        else:
            shutil.copy2(str(old_anno), str(new_anno))
            print(f"  ✓ Copied successfully")
    else:
        print(f"  ✗ {old_anno} not found")

    # 3. 准备 institutions.json
    old_inst = base_dir / "data" / "institution.json"
    new_inst = base_dir / "data" / "institutions.json"

    if old_inst.exists() and not new_inst.exists():
        print(f"\nCopying {old_inst.name} → {new_inst.name}")
        shutil.copy2(str(old_inst), str(new_inst))
        print(f"  ✓ Copied successfully")

    # 4. 创建空的 events.json
    events_file = base_dir / "data" / "events.json"
    if not events_file.exists():
        print(f"\nCreating {events_file.name}")
        events_data = {
            "total": 0,
            "last_updated": None,
            "events": []
        }
        with open(events_file, "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Created successfully")

    print("\n" + "="*60)
    print("Data migration completed!")
    print("="*60)


if __name__ == "__main__":
    migrate_data_directories()
