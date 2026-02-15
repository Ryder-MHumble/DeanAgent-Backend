"""One-time migration: convert date-based JSON files to latest.json format.

For each source directory under data/raw/, this script:
1. Finds all {YYYY-MM-DD}.json files
2. Takes the most recent one as the basis for latest.json
3. Adds is_new=false to all items and new metadata fields
4. Deletes old date-based files
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
LATEST_FILENAME = "latest.json"


def migrate():
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        return

    migrated = 0
    skipped = 0

    for source_dir in sorted(DATA_DIR.rglob("*")):
        if not source_dir.is_dir():
            continue

        date_files = sorted(
            [f for f in source_dir.iterdir() if DATE_PATTERN.match(f.name)],
            key=lambda f: f.name,
            reverse=True,
        )
        if not date_files:
            continue

        latest_path = source_dir / LATEST_FILENAME
        if latest_path.exists():
            print(f"  SKIP {source_dir.relative_to(DATA_DIR)}: latest.json already exists")
            skipped += 1
            # Still remove old date files even if latest.json exists
            for old_file in date_files:
                old_file.unlink()
                print(f"    Removed {old_file.name}")
            continue

        newest = date_files[0]

        try:
            with open(newest, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ERROR {source_dir.relative_to(DATA_DIR)}: {e}")
            continue

        for item in data.get("items", []):
            item["is_new"] = False

        data["previous_crawled_at"] = None
        data["new_item_count"] = 0

        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        for old_file in date_files:
            old_file.unlink()

        item_count = len(data.get("items", []))
        rel = source_dir.relative_to(DATA_DIR)
        print(
            f"  OK   {rel}: {len(date_files)} date file(s) -> latest.json "
            f"({item_count} items)"
        )
        migrated += 1

    print(f"\nDone: {migrated} migrated, {skipped} skipped (already had latest.json)")


if __name__ == "__main__":
    print("=== Migrating date-based JSON files to latest.json ===\n")
    migrate()
