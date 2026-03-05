"""Institution data builder — generates institutions.json from YAML configs + scholar counts."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.scheduler.manager import load_all_source_configs
from app.services.stores.source_state import get_all_source_states


def _normalize_university_id(name: str) -> str:
    """Normalize university name to ID (e.g., '清华大学' → 'tsinghua')."""
    mapping = {
        "清华大学": "tsinghua",
        "北京大学": "pku",
        "南京大学": "nju",
        "浙江大学": "zju",
        "中国科学院": "cas",
        "复旦大学": "fudan",
        "中国人民大学": "ruc",
        "上海交通大学": "sjtu",
        "中国科学技术大学": "ustc",
    }
    return mapping.get(name, name.lower().replace(" ", "_"))


def _normalize_department_id(university_id: str, dept_name: str) -> str:
    """Normalize department name to ID."""
    dept_normalized = dept_name.lower().replace(" ", "_").replace("、", "_")
    return f"{university_id}_{dept_normalized}"


def _count_scholars_in_source(source_id: str, group: str) -> int:
    """Count scholars in a specific source by reading its latest.json."""
    try:
        raw_path = Path("data/scholars") / group / source_id / "latest.json"
        if not raw_path.exists():
            return 0
        with open(raw_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("item_count", len(data.get("items", [])))
    except (json.JSONDecodeError, OSError, KeyError):
        return 0


def build_institutions_data() -> dict[str, Any]:
    """Build institutions data from YAML configs + scholar counts.

    IMPORTANT: This function now MERGES with existing institutions.json data
    instead of overwriting it. It only updates scholar_count and departments,
    preserving all other fields (category, priority, student_count, etc.)

    Returns:
        Dictionary with structure:
        {
            "last_updated": "ISO timestamp",
            "universities": [
                {
                    "id": "tsinghua",
                    "name": "清华大学",
                    "scholar_count": 156,
                    "departments": [...],
                    # ... other fields preserved from existing data
                }
            ]
        }
    """
    # Load existing institutions.json if it exists
    existing_data = {}
    institutions_file = Path("data/scholars/institutions.json")
    if institutions_file.exists():
        try:
            with open(institutions_file, encoding="utf-8") as f:
                existing_json = json.load(f)
                # Build lookup by university name
                for uni in existing_json.get("universities", []):
                    existing_data[uni["name"]] = uni
        except (json.JSONDecodeError, OSError):
            pass

    configs = load_all_source_configs()
    states = get_all_source_states()

    # Filter to scholar sources only
    scholar_configs = [c for c in configs if c.get("dimension") == "scholars"]

    # Group by (university, department)
    uni_dept_map: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for cfg in scholar_configs:
        university = cfg.get("university", "")
        department = cfg.get("department", "")

        if not university or not department:
            continue

        key = (university, department)
        uni_dept_map[key].append(cfg)

    # Build universities structure
    universities_by_name: dict[str, dict[str, Any]] = {}

    for (university_name, _), sources in sorted(uni_dept_map.items()):
        if university_name not in universities_by_name:
            # Start with existing data if available
            if university_name in existing_data:
                universities_by_name[university_name] = existing_data[university_name].copy()
                universities_by_name[university_name]["scholar_count"] = 0
                universities_by_name[university_name]["departments"] = {}
            else:
                universities_by_name[university_name] = {
                    "id": _normalize_university_id(university_name),
                    "name": university_name,
                    "org_name": None,
                    "scholar_count": 0,
                    "departments": {},
                }

        uni_data = universities_by_name[university_name]

        # Group sources by department
        dept_map: dict[str, list[dict]] = defaultdict(list)
        for src in sources:
            dept = src.get("department", "")
            dept_map[dept].append(src)

        # Build departments
        for dept_name, dept_sources in sorted(dept_map.items()):
            dept_id = _normalize_department_id(uni_data["id"], dept_name)

            dept_scholar_count = 0
            source_items = []

            for src in dept_sources:
                source_id = src.get("id", "")
                group = src.get("group", "")
                state = states.get(source_id, {})

                # Determine if enabled
                override = state.get("is_enabled_override")
                is_enabled = override if override is not None else src.get("is_enabled", True)

                # Count scholars
                scholar_count = _count_scholars_in_source(source_id, group)
                dept_scholar_count += scholar_count

                source_items.append({
                    "source_id": source_id,
                    "source_name": src.get("name", source_id),
                    "scholar_count": scholar_count,
                    "is_enabled": is_enabled,
                    "last_crawl_at": state.get("last_crawl_at"),
                })

            uni_data["departments"][dept_id] = {
                "id": dept_id,
                "name": dept_name,
                "scholar_count": dept_scholar_count,
                "sources": source_items,
                "org_name": None,  # Will be filled by AMiner enrichment
            }

            uni_data["scholar_count"] += dept_scholar_count

    # Convert to list format
    universities = []
    for uni_data in universities_by_name.values():
        uni_data["departments"] = list(uni_data["departments"].values())
        universities.append(uni_data)

    # Add universities from existing data that don't have scholar sources
    for uni_name, uni_data in existing_data.items():
        if uni_name not in universities_by_name:
            universities.append(uni_data)

    return {
        "last_updated": datetime.now(UTC).isoformat(),
        "universities": sorted(universities, key=lambda u: u["name"]),
    }


def save_institutions_data(data: dict[str, Any] | None = None) -> Path:
    """Build and save institutions.json.

    Args:
        data: Pre-built institutions data. If None, builds from scratch.

    Returns:
        Path to saved institutions.json
    """
    if data is None:
        data = build_institutions_data()

    output_path = Path("data/scholars/institutions.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path
