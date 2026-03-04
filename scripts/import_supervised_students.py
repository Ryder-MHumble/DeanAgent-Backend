"""Import supervised students from CSV files into supervised_students.json.

Source files (data/):
  24级学生数据.csv  — columns: 学号, 学生姓名, 推荐高校, 导师姓名, 导师职称, 导师邮箱
  25级学生数据.csv  — columns: 学号, 姓名, 学籍高校, 拟报博士导师姓名, 导师职称, 导师邮箱
  26级学生数据.csv  — columns: 姓名, 批次, 学生类别, 确认接受高校, 确认接受专业, 导师姓名

Output:
  data/state/supervised_students.json  — students grouped by faculty url_hash
    * Only students whose advisor name matches a faculty in the database are written.
    * Students with unmatched advisors are reported in a summary at the end.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "state" / "supervised_students.json"
CREATED_AT = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Build faculty name → url_hash lookup from raw JSON files
# ---------------------------------------------------------------------------

def _build_name_map() -> dict[str, str]:
    """Return {faculty_name: url_hash} from all university_faculty raw JSON files."""
    name_map: dict[str, str] = {}
    faculty_dir = DATA_DIR / "raw" / "scholars"
    if not faculty_dir.exists():
        print(f"[WARN] Faculty dir not found: {faculty_dir}", file=sys.stderr)
        return name_map

    for json_file in faculty_dir.rglob("latest.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for item in payload.get("items", []):
            extra = item.get("extra", {})
            name = extra.get("name", "").strip()
            url_hash = item.get("url_hash", "").strip()
            if name and url_hash and name not in name_map:
                name_map[name] = url_hash

    return name_map


# ---------------------------------------------------------------------------
# 2. Helpers
# ---------------------------------------------------------------------------

def _make_record(
    student_no: str,
    name: str,
    home_university: str,
    degree_type: str,
    enrollment_year: str,
    status: str = "在读",
    notes: str = "",
) -> dict:
    return {
        "id": str(uuid4()),
        "student_no": student_no.strip(),
        "name": name.strip(),
        "home_university": home_university.strip(),
        "degree_type": degree_type,
        "enrollment_year": enrollment_year,
        "expected_graduation_year": "",
        "status": status,
        "email": "",
        "phone": "",
        "notes": notes,
        "added_by": "user:import_script",
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def _enrollment_year_from_type(student_type: str) -> str:
    """Extract enrollment year from 26级 学生类别.

    Examples:
      '2026级直博'            -> '2026'
      '在读博士-2025级普博'   -> '2025'
    """
    match = re.search(r"(\d{4})级", student_type)
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# 3. Parse CSV files
# ---------------------------------------------------------------------------

def _parse_24(name_map: dict[str, str]) -> tuple[dict[str, list], list[str]]:
    """Return (matched: {url_hash: [records]}, unmatched: [advisor_name...])."""
    path = DATA_DIR / "24级学生数据.csv"
    matched: dict[str, list] = {}
    unmatched: list[str] = []

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            # Skip rows without a name (noise / blank rows)
            name = row[1].strip() if len(row) > 1 else ""
            if not name:
                continue
            student_no = row[0].strip() if len(row) > 0 else ""
            home_uni = row[2].strip() if len(row) > 2 else ""
            advisor = row[3].strip() if len(row) > 3 else ""

            record = _make_record(
                student_no=student_no,
                name=name,
                home_university=home_uni,
                degree_type="博士",
                enrollment_year="2024",
            )

            if advisor and advisor in name_map:
                matched.setdefault(name_map[advisor], []).append(record)
            else:
                if advisor:
                    unmatched.append(advisor)

    return matched, unmatched


def _parse_25(name_map: dict[str, str]) -> tuple[dict[str, list], list[str]]:
    path = DATA_DIR / "25级学生数据.csv"
    matched: dict[str, list] = {}
    unmatched: list[str] = []

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            name = row[1].strip() if len(row) > 1 else ""
            if not name:
                continue
            student_no = row[0].strip() if len(row) > 0 else ""
            home_uni = row[2].strip() if len(row) > 2 else ""
            advisor = row[3].strip() if len(row) > 3 else ""

            record = _make_record(
                student_no=student_no,
                name=name,
                home_university=home_uni,
                degree_type="博士",
                enrollment_year="2025",
            )

            if advisor and advisor in name_map:
                matched.setdefault(name_map[advisor], []).append(record)
            else:
                if advisor:
                    unmatched.append(advisor)

    return matched, unmatched


def _parse_26(name_map: dict[str, str]) -> tuple[dict[str, list], list[str]]:
    path = DATA_DIR / "26级学生数据.csv"
    matched: dict[str, list] = {}
    unmatched: list[str] = []

    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["姓名"].strip()
            if not name:
                continue
            home_uni = row["确认接受高校"].strip()
            student_type = row["学生类别"].strip()
            advisor = row["导师姓名"].strip()
            enrollment_year = _enrollment_year_from_type(student_type)

            record = _make_record(
                student_no="",
                name=name,
                home_university=home_uni,
                degree_type="博士",
                enrollment_year=enrollment_year,
                notes=f"学生类别: {student_type}" if student_type else "",
            )

            if advisor and advisor in name_map:
                matched.setdefault(name_map[advisor], []).append(record)
            else:
                if advisor:
                    unmatched.append(advisor)

    return matched, unmatched


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Building faculty name lookup...")
    name_map = _build_name_map()
    print(f"  Faculty records loaded: {len(name_map)}")

    print("Parsing CSV files...")
    m24, u24 = _parse_24(name_map)
    m25, u25 = _parse_25(name_map)
    m26, u26 = _parse_26(name_map)

    # Merge all matched results (same faculty url_hash from multiple years)
    all_matched: dict[str, list] = {}
    for source in (m24, m25, m26):
        for url_hash, records in source.items():
            all_matched.setdefault(url_hash, []).extend(records)

    # Stats
    total_matched = sum(len(v) for v in all_matched.values())
    all_unmatched = list(set(u24 + u25 + u26))

    c24 = sum(len(v) for v in m24.values())
    c25 = sum(len(v) for v in m25.values())
    c26 = sum(len(v) for v in m26.values())
    print(f"\n  24级 matched: {c24}, unmatched advisors: {len(set(u24))}")
    print(f"  25级 matched: {c25}, unmatched advisors: {len(set(u25))}")
    print(f"  26级 matched: {c26}, unmatched advisors: {len(set(u26))}")
    print(f"\n  Total matched students: {total_matched}")
    print(f"  Faculty with students: {len(all_matched)}")
    print(f"  Unmatched advisor names (not in faculty DB): {len(all_unmatched)}")
    print("  (Unmatched students excluded — add advisors to faculty DB and re-run)")

    # Load existing file to preserve any manually-added records
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"\n  Existing file has {len(existing)} faculty entries — merging...")
        # Merge: existing records kept, CSV records appended only if not duplicate name
        for url_hash, records in all_matched.items():
            existing_names = {r["name"] for r in existing.get(url_hash, [])}
            new_records = [r for r in records if r["name"] not in existing_names]
            if new_records:
                existing.setdefault(url_hash, []).extend(new_records)
        output = existing
    else:
        output = all_matched

    # Write
    tmp = OUTPUT_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp.replace(OUTPUT_FILE)

    total_final = sum(len(v) for v in output.values())
    print(f"\nWritten to: {OUTPUT_FILE}")
    print(f"  Total students in file: {total_final}")
    print(f"  Faculty entries: {len(output)}")


if __name__ == "__main__":
    main()
