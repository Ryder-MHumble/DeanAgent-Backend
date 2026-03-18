#!/usr/bin/env python3
"""Import scholars from scholars_final_complete.csv into Supabase database.

Maps CSV columns to ScholarRecord schema fields and imports data with proper
field transformations, deduplication, and error handling.

CSV Columns → Schema Fields Mapping:
- 英文姓名 → name_en
- 中文姓名 → name (required)
- 机构_英文 → (parsed to university/department)
- 机构_中文 → university, department
- 机构_国家 → (stored in custom_fields)
- 机构_ID → (stored in custom_fields as aminer_org_id)
- 主页 → profile_url
- 邮箱 → email
- 电话 → phone
- 头像 → photo_url
- 职称 → position
- H指数 → h_index
- 被引次数 → citations_count
- 研究方向 → research_areas (JSON array)
- 简介 → bio
- 教育经历 → education (parsed)
- 荣誉 → awards (JSON array)
- 工作经历 → (stored in bio or custom_fields)
- AMiner_ID → (stored in custom_fields)
"""
import asyncio
import csv
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.db.client import get_client, init_client
from app.schemas.scholar import (
    AwardRecord,
    EducationRecord,
    ScholarRecord,
    compute_scholar_completeness,
)

# Load environment variables
load_dotenv()


def normalize_url(url: str) -> str:
    """Normalize URL for consistent hashing."""
    if not url:
        return ""
    url = url.strip().lower()
    # Remove trailing slashes
    url = url.rstrip("/")
    # Remove common query params
    url = re.sub(r"[?&](utm_|ref=|source=).*", "", url)
    return url


def compute_url_hash(url: str) -> str:
    """Compute SHA-256 hash of normalized URL."""
    normalized = normalize_url(url)
    if not normalized:
        # If no profile_url, use name + email as fallback
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_json_field(value: str) -> list:
    """Parse JSON string field, return empty list if invalid."""
    if not value or value.strip() == "":
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def parse_research_areas(value: str) -> list[str]:
    """Parse research areas from JSON array string."""
    areas = parse_json_field(value)
    # Clean and deduplicate
    cleaned = []
    seen = set()
    for area in areas:
        if isinstance(area, str):
            area = area.strip()
            if area and area not in seen:
                cleaned.append(area)
                seen.add(area)
    return cleaned


def parse_education(value: str) -> list[EducationRecord]:
    """Parse education field into EducationRecord list.

    Expected format: "学位（学校）<br>学位（学校）<br>..."
    Example: "理学学士（普林斯顿大学）<br>理学硕士（斯坦福大学）<br>哲学博士（斯坦福大学）"
    """
    if not value or value.strip() == "":
        return []

    records = []
    # Split by <br> or newline
    parts = re.split(r"<br>|<br/>|\n", value)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Try to extract degree and institution
        # Pattern: 学位（学校）or 学位, 学校
        match = re.search(r"([^（(]+)[（(]([^)）]+)[)）]", part)
        if match:
            degree = match.group(1).strip()
            institution = match.group(2).strip()
            records.append(EducationRecord(
                degree=degree,
                institution=institution,
                year="",
                major=""
            ))
        else:
            # Fallback: treat entire string as degree
            records.append(EducationRecord(
                degree=part,
                institution="",
                year="",
                major=""
            ))

    return records


def parse_awards(value: str) -> list[AwardRecord]:
    """Parse awards from JSON array string.

    Expected format: JSON array of award objects with fields:
    - award: award name
    - year: year
    - reason: description
    """
    awards_data = parse_json_field(value)
    if not awards_data:
        return []

    records = []
    for item in awards_data:
        if not isinstance(item, dict):
            continue

        award_name = item.get("award", "")
        year = item.get("year")
        reason = item.get("reason", "")

        # Convert year to string
        year_str = str(year) if year else ""

        records.append(AwardRecord(
            title=award_name,
            year=year_str,
            level="",
            grantor="",
            description=reason,
            added_by="csv_import"
        ))

    return records


def parse_institution(org_cn: str, org_en: str) -> tuple[str, str]:
    """Parse university and department from institution strings.

    Returns: (university, department)
    """
    # Prefer Chinese name
    org = org_cn if org_cn else org_en
    if not org:
        return "", ""

    # Try to split by comma (department, university)
    if "," in org:
        parts = org.split(",", 1)
        if len(parts) == 2:
            # Format: "University, Department" or "Department, University"
            # Check which is which by common keywords
            part1, part2 = parts[0].strip(), parts[1].strip()

            # If part2 contains department keywords, swap
            dept_keywords = ["学院", "系", "所", "中心", "School", "Department", "College", "Institute"]
            if any(kw in part2 for kw in dept_keywords):
                return part1, part2
            else:
                return part2, part1

    # No comma, treat entire string as university
    return org, ""


def safe_int(value: str, default: int = -1) -> int:
    """Convert string to int, return default if invalid."""
    if not value or value.strip() == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


async def import_scholars_from_csv(csv_path: Path, dry_run: bool = False):
    """Import scholars from CSV file into database."""

    print(f"Reading CSV file: {csv_path}")

    # Read CSV
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} rows in CSV")

    # Initialize database client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

    await init_client(supabase_url, supabase_key)
    client = get_client()

    # Statistics
    stats = {
        "total": len(rows),
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "errors": []
    }

    now = datetime.now(timezone.utc).isoformat()

    for idx, row in enumerate(rows, start=1):
        try:
            # Extract fields
            name_en = row.get("英文姓名", "").strip()
            name_cn = row.get("中文姓名", "").strip()
            org_en = row.get("机构_英文", "").strip()
            org_cn = row.get("机构_中文", "").strip()
            org_country = row.get("机构_国家", "").strip()
            org_id = row.get("机构_ID", "").strip()
            profile_url = row.get("主页", "").strip()
            email = row.get("邮箱", "").strip()
            phone = row.get("电话", "").strip()
            photo_url = row.get("头像", "").strip()
            position = row.get("职称", "").strip()
            h_index_str = row.get("H指数", "").strip()
            citations_str = row.get("被引次数", "").strip()
            research_areas_str = row.get("研究方向", "").strip()
            bio = row.get("简介", "").strip()
            education_str = row.get("教育经历", "").strip()
            awards_str = row.get("荣誉", "").strip()
            work_exp = row.get("工作经历", "").strip()
            aminer_id = row.get("AMiner_ID", "").strip()
            gender = ""  # Not in CSV, default to empty

            # Validate required fields
            if not name_cn and not name_en:
                stats["skipped"] += 1
                stats["errors"].append(f"Row {idx}: Missing both Chinese and English name")
                continue

            # Use Chinese name as primary, fallback to English
            name = name_cn if name_cn else name_en

            # Parse institution
            university, department = parse_institution(org_cn, org_en)

            # Check for duplicate by profile_url or email
            # Priority: profile_url > email
            if profile_url:
                existing = await client.table("scholars").select("id").eq("profile_url", profile_url).execute()
                if existing.data:
                    stats["skipped"] += 1
                    print(f"Row {idx}: Skipped (duplicate profile_url) - {name}")
                    continue
            elif email:
                existing = await client.table("scholars").select("id").eq("email", email).execute()
                if existing.data:
                    stats["skipped"] += 1
                    print(f"Row {idx}: Skipped (duplicate email) - {name}")
                    continue

            # Also check by name + university to avoid duplicates
            if name and university:
                existing = await client.table("scholars").select("id").eq("name", name).eq("university", university).execute()
                if existing.data:
                    stats["skipped"] += 1
                    print(f"Row {idx}: Skipped (duplicate name+university) - {name}")
                    continue

            # Parse complex fields
            research_areas = parse_research_areas(research_areas_str)
            education = parse_education(education_str)
            awards = parse_awards(awards_str)
            h_index = safe_int(h_index_str, -1)
            citations_count = safe_int(citations_str, -1)

            # Extract PhD info from education
            phd_institution = ""
            phd_year = ""
            for edu in education:
                if "博士" in edu.degree or "PhD" in edu.degree or "Ph.D" in edu.degree:
                    phd_institution = edu.institution
                    phd_year = edu.year
                    break

            # Build ScholarRecord
            scholar = ScholarRecord(
                name=name,
                name_en=name_en,
                gender="",
                photo_url=photo_url,
                university=university,
                department=department,
                secondary_departments=[],
                position=position,
                academic_titles=[],
                is_academician=False,
                research_areas=research_areas,
                keywords=[],
                bio=bio,
                bio_en="",
                email=email,
                phone=phone,
                office="",
                profile_url=profile_url,
                lab_url="",
                google_scholar_url="",
                dblp_url="",
                orcid="",
                phd_institution=phd_institution,
                phd_year=phd_year,
                education=education,
                publications_count=-1,
                h_index=h_index,
                citations_count=citations_count,
                metrics_updated_at=now if h_index > 0 or citations_count > 0 else "",
                representative_publications=[],
                patents=[],
                awards=awards,
                is_advisor_committee=False,
                supervised_students=[],
                joint_research_projects=[],
                joint_management_roles=[],
                academic_exchange_records=[],
                is_potential_recruit=False,
                institute_relation_notes="",
                relation_updated_by="",
                relation_updated_at="",
                recent_updates=[],
                source_id="csv_import",
                source_url=csv_path.name,
                crawled_at=now,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
                data_completeness=0,
            )

            # Compute completeness
            scholar.data_completeness = compute_scholar_completeness(scholar)

            # Generate UUID for the scholar
            scholar_id = str(uuid.uuid4())

            # Prepare database row (scholars table has direct columns, not articles-style structure)
            db_row = {
                "id": scholar_id,
                "name": name,
                "name_en": name_en or None,
                "gender": gender or None,
                "photo_url": photo_url or None,
                "university": university or None,
                "department": department or None,
                "secondary_departments": [],
                "position": position or None,
                "academic_titles": [],
                "is_academician": False,
                "research_areas": research_areas,
                "keywords": [],
                "bio": bio or None,
                "bio_en": None,
                "email": email or None,
                "phone": phone or None,
                "office": None,
                "profile_url": profile_url or None,
                "lab_url": None,
                "google_scholar_url": None,
                "dblp_url": None,
                "orcid": None,
                "phd_institution": phd_institution or None,
                "phd_year": phd_year or None,
                "publications_count": None,
                "h_index": h_index if h_index >= 0 else None,
                "citations_count": citations_count if citations_count >= 0 else None,
                "metrics_updated_at": now if h_index > 0 or citations_count > 0 else None,
                "is_advisor_committee": False,
                "is_potential_recruit": False,
                "adjunct_supervisor": {},
                "joint_research_projects": [],
                "joint_management_roles": [],
                "academic_exchange_records": [],
                "institute_relation_notes": None,
                "relation_updated_by": None,
                "relation_updated_at": None,
                "source_id": "csv_import",
                "source_url": csv_path.name,
                "crawled_at": now,
                "first_seen_at": now,
                "last_seen_at": now,
                "is_active": True,
                "data_completeness": scholar.data_completeness,
                "content": bio or None,
                "tags": [],
                "representative_publications": [pub.model_dump() for pub in scholar.representative_publications],
                "patents": [pat.model_dump() for pat in scholar.patents],
                "awards": [award.model_dump() for award in awards],
                "education": [edu.model_dump() for edu in education],
                "recent_updates": [],
                "supervised_students": [],
                "custom_fields": {
                    "org_country": org_country,
                    "aminer_org_id": org_id,
                    "aminer_id": aminer_id,
                    "work_experience": work_exp,
                    "import_source": "scholars_final_complete.csv",
                    "import_date": now,
                },
                "project_category": None,
                "project_subcategory": None,
            }

            if dry_run:
                print(f"Row {idx}: [DRY RUN] Would import {name} ({university})")
                stats["success"] += 1
            else:
                # Insert into database
                try:
                    result = await client.table("scholars").insert(db_row).execute()
                    if result.data:
                        stats["success"] += 1
                        print(f"Row {idx}: ✓ Imported {name} ({university})")
                    else:
                        stats["failed"] += 1
                        stats["errors"].append(f"Row {idx}: Database insert failed for {name}")
                except Exception as e:
                    stats["failed"] += 1
                    error_msg = f"Row {idx}: Database error - {str(e)}"
                    stats["errors"].append(error_msg)
                    print(f"✗ {error_msg}")
                    # Debug: print the problematic row
                    import json
                    print(f"Debug row data: {json.dumps(db_row, indent=2, default=str)[:500]}")
                    raise  # Re-raise to see full traceback

        except Exception as e:
            stats["failed"] += 1
            error_msg = f"Row {idx}: Error - {str(e)}"
            stats["errors"].append(error_msg)
            print(f"✗ {error_msg}")

    # Print summary
    print("\n" + "=" * 60)
    print("Import Summary")
    print("=" * 60)
    print(f"Total rows:     {stats['total']}")
    print(f"Success:        {stats['success']}")
    print(f"Skipped:        {stats['skipped']}")
    print(f"Failed:         {stats['failed']}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats["errors"][:20]:  # Show first 20 errors
            print(f"  - {error}")
        if len(stats["errors"]) > 20:
            print(f"  ... and {len(stats['errors']) - 20} more errors")

    return stats


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import scholars from CSV")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/scholars_final_complete.csv"),
        help="Path to CSV file (default: data/scholars_final_complete.csv)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't actually insert into database)"
    )

    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}")
        return

    await import_scholars_from_csv(args.csv, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
