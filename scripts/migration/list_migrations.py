#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure repo root is importable when executed as a file path.
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.migration.catalog import CAPABILITY_LABELS, MIGRATION_CATALOG, REUSE_LABELS


def _build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in MIGRATION_CATALOG:
        rows.append(
            {
                "file": item.file,
                "capability": CAPABILITY_LABELS.get(item.capability, item.capability),
                "reuse": REUSE_LABELS.get(item.reuse, item.reuse),
                "status": item.status,
                "canonical": "yes" if item.canonical else "no",
                "superseded_by": item.superseded_by or "",
                "description": item.description,
            }
        )
    return rows


def _print_table(rows: list[dict[str, str]]) -> None:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["capability"]].append(row)

    for capability in sorted(groups.keys()):
        print(f"\n[{capability}]")
        print("file | reuse | status | canonical | superseded_by")
        print("-----|-------|--------|-----------|-------------")
        for row in sorted(groups[capability], key=lambda x: x["file"]):
            print(
                f"{row['file']} | {row['reuse']} | {row['status']} | "
                f"{row['canonical']} | {row['superseded_by']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="List migration scripts by capability/reuse.")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args()

    rows = _build_rows()
    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    _print_table(rows)


if __name__ == "__main__":
    main()
