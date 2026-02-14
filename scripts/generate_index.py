"""Generate data/index.json — unified index mapping sources to their crawled data files.

Usage:
    python scripts/generate_index.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "sources"
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
INDEX_PATH = BASE_DIR / "data" / "index.json"

DIMENSION_NAMES = {
    "national_policy": "对国家",
    "beijing_policy": "对北京",
    "technology": "对技术",
    "talent": "对人才",
    "industry": "对产业",
    "sentiment": "对学院舆情",
    "universities": "对高校",
    "events": "对日程",
    "personnel": "对人事",
}


def load_yaml_sources() -> dict[str, dict]:
    """Load all YAML configs, keyed by source_id."""
    sources: dict[str, dict] = {}
    for yaml_file in sorted(SOURCES_DIR.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        if data is None:
            continue

        dimension = data.get("dimension", yaml_file.stem)
        for src in data.get("sources", []):
            src.setdefault("dimension", dimension)
            sources[src["id"]] = src
    return sources


def scan_data_files(source_id: str, dimension: str, group: str) -> dict:
    """Scan data/raw/ for actual files of a given source."""
    source_dir = RAW_DATA_DIR / dimension / group / source_id
    if not source_dir.is_dir():
        return {"data_path": str(source_dir.relative_to(BASE_DIR)) + "/", "files": [], "article_count": 0}

    files = sorted(source_dir.glob("*.json"))
    total_articles = 0
    file_entries = []
    for f in files:
        try:
            with open(f) as fp:
                content = json.load(fp)
            count = content.get("item_count", len(content.get("items", [])))
        except (json.JSONDecodeError, OSError):
            count = 0

        file_entries.append({"date": f.stem, "article_count": count})
        total_articles += count

    return {
        "data_path": str(source_dir.relative_to(BASE_DIR)) + "/",
        "files": file_entries,
        "article_count": total_articles,
    }


def generate_index() -> dict:
    yaml_sources = load_yaml_sources()

    dimensions: dict[str, dict] = {}
    total_sources = 0
    total_enabled = 0
    total_articles = 0

    for source_id, config in yaml_sources.items():
        dim = config["dimension"]
        group = config.get("group", "default")
        enabled = config.get("is_enabled", True)
        crawl_method = config.get("crawl_method", "static")
        crawler_class = config.get("crawler_class")

        if dim not in dimensions:
            dimensions[dim] = {
                "name": DIMENSION_NAMES.get(dim, dim),
                "source_count": 0,
                "enabled_count": 0,
                "article_count": 0,
                "sources": [],
            }

        file_info = scan_data_files(source_id, dim, group)

        source_entry = {
            "source_id": source_id,
            "source_name": config.get("name", source_id),
            "group": group,
            "crawl_method": crawl_method,
            "enabled": enabled,
            "url": config.get("url", ""),
            "schedule": config.get("schedule", "daily"),
            "data_path": file_info["data_path"],
            "files": file_info["files"],
            "article_count": file_info["article_count"],
        }
        if crawler_class:
            source_entry["crawler_class"] = crawler_class

        dimensions[dim]["sources"].append(source_entry)
        dimensions[dim]["source_count"] += 1
        dimensions[dim]["article_count"] += file_info["article_count"]
        if enabled:
            dimensions[dim]["enabled_count"] += 1

        total_sources += 1
        if enabled:
            total_enabled += 1
        total_articles += file_info["article_count"]

    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sources": total_sources,
        "total_enabled": total_enabled,
        "total_articles": total_articles,
        "dimensions": dimensions,
    }
    return index


def main() -> None:
    index = generate_index()
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Generated {INDEX_PATH}")
    print(f"  Total sources: {index['total_sources']} ({index['total_enabled']} enabled)")
    print(f"  Total articles: {index['total_articles']}")
    print(f"  Dimensions: {len(index['dimensions'])}")


if __name__ == "__main__":
    main()
