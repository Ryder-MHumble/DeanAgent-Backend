"""Validate faculty crawler output and compute quality metrics."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.scholar import ScholarRecord, compute_scholar_completeness


def validate_source(source_id: str) -> bool:
    """Validate a faculty source's output JSON.

    Args:
        source_id: Source ID to validate (e.g., 'tsinghua_air_faculty')

    Returns:
        True if validation passes (avg completeness >= 60), False otherwise
    """
    # Find the latest.json file for this source
    data_root = Path(__file__).resolve().parent.parent / "data" / "raw" / "university_faculty"

    # Search all subdirectories for matching source_id
    json_files = list(data_root.rglob(f"{source_id}/latest.json"))

    if not json_files:
        print(f"❌ ERROR: No latest.json found for source '{source_id}'")
        print(f"   Searched in: {data_root}")
        return False

    if len(json_files) > 1:
        print(f"⚠️  WARNING: Multiple files found for '{source_id}', using first match")

    json_path = json_files[0]
    print(f"📂 Reading: {json_path}\n")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ ERROR: Failed to read JSON file: {e}")
        return False

    items = data.get("items", [])
    if not items:
        print(f"❌ ERROR: No items found in JSON file")
        return False

    # Extract ScholarRecord from each item's extra field and compute completeness
    scores = []
    missing_fields = Counter()

    for idx, item in enumerate(items, 1):
        extra = item.get("extra", {})
        if not extra:
            print(f"⚠️  WARNING: Item {idx} has no 'extra' field, skipping")
            continue

        try:
            scholar = ScholarRecord(**extra)
            score = compute_scholar_completeness(scholar)
            scores.append(score)

            # Track missing critical fields
            if not scholar.name:
                missing_fields["name"] += 1
            if not scholar.bio:
                missing_fields["bio"] += 1
            if not scholar.email:
                missing_fields["email"] += 1
            if not scholar.research_areas:
                missing_fields["research_areas"] += 1

        except Exception as e:
            print(f"⚠️  WARNING: Failed to parse item {idx} as ScholarRecord: {e}")
            continue

    if not scores:
        print(f"❌ ERROR: No valid ScholarRecord items found")
        return False

    # Compute statistics
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)
    faculty_count = len(scores)

    # Print report header
    print("=" * 70)
    print(f"FACULTY DATA VALIDATION REPORT")
    print(f"Source: {source_id}")
    print(f"File: {json_path.relative_to(Path.cwd())}")
    print("=" * 70)
    print()

    # Print basic statistics
    print(f"📊 STATISTICS")
    print(f"   Faculty count:      {faculty_count}")
    print(f"   Average completeness: {avg_score:.1f}%")
    print(f"   Min completeness:   {min_score}%")
    print(f"   Max completeness:   {max_score}%")
    print()

    # Print missing fields breakdown
    if missing_fields:
        print(f"🔍 MISSING FIELDS BREAKDOWN")
        print(f"   {'Field':<20} {'Missing Count':<15} {'Percentage'}")
        print(f"   {'-' * 20} {'-' * 15} {'-' * 10}")
        for field, count in missing_fields.most_common():
            pct = (count / faculty_count) * 100
            print(f"   {field:<20} {count:<15} {pct:>6.1f}%")
        print()

    # Quality assessment
    print(f"✅ QUALITY ASSESSMENT")
    if avg_score >= 70:
        status = "✅ PASS (Excellent)"
        passed = True
    elif avg_score >= 60:
        status = "⚠️  PASS (Acceptable)"
        passed = True
    elif avg_score >= 40:
        status = "⚠️  WARNING (Needs improvement)"
        passed = False
    else:
        status = "❌ FAIL (Poor quality)"
        passed = False

    print(f"   Status: {status}")
    print(f"   Average completeness: {avg_score:.1f}%")
    print()

    # Print scoring thresholds for reference
    print(f"📋 SCORING THRESHOLDS")
    print(f"   ✅ PASS (Excellent):     >= 70%")
    print(f"   ⚠️  PASS (Acceptable):    >= 60%")
    print(f"   ⚠️  WARNING:              40-60%")
    print(f"   ❌ FAIL:                  < 40%")
    print()

    print("=" * 70)

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate faculty crawler output and compute quality metrics"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source ID to validate (e.g., 'tsinghua_air_faculty')"
    )
    args = parser.parse_args()

    success = validate_source(args.source)
    sys.exit(0 if success else 1)