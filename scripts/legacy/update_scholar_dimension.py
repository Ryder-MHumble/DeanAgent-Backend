#!/usr/bin/env python3
"""Batch update dimension field in all scholar JSON files from 'university_faculty' to 'scholars'."""
import json
from pathlib import Path


def update_dimension_in_json():
    """Batch update data/scholars/ JSON files' dimension field."""
    scholars_dir = Path("data/scholars")
    if not scholars_dir.exists():
        print(f"❌ Directory not found: {scholars_dir}")
        return

    updated_count = 0
    total_count = 0

    for json_file in sorted(scholars_dir.rglob("latest.json")):
        total_count += 1
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            old_dimension = data.get("dimension")
            if old_dimension == "university_faculty":
                data["dimension"] = "scholars"
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                updated_count += 1
                print(f"✅ Updated: {json_file}")
            elif old_dimension == "scholars":
                print(f"⏭️  Already updated: {json_file}")
            else:
                print(f"⚠️  Unexpected dimension '{old_dimension}': {json_file}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"❌ Error processing {json_file}: {e}")

    print(f"\n📊 Summary: {updated_count}/{total_count} files updated")


if __name__ == "__main__":
    update_dimension_in_json()
