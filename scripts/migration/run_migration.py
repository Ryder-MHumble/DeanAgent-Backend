#!/usr/bin/env python3
"""Run migration scripts via catalog metadata.

Examples:
  python scripts/migration/run_migration.py --list
  python scripts/migration/run_migration.py --run fix_scholar_institutions.py --dry-run
  python scripts/migration/run_migration.py --run fix_scholar_institutions.py --apply -- --scope global
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.migration.catalog import MIGRATION_CATALOG

_SUPPORTS_DRY_RUN = {
    "import_adjunct_mentors.py",
    "import_students_from_xlsx.py",
    "migrate_scholar_achievements.py",
    "tag_scholars_from_academy_mentors_csv.py",
    "init_event_taxonomy.py",
    "archive/oneoff/migrate_event_categories.py",
    "archive/oneoff/rename_cas_to_ucas.py",
    "archive/oneoff/tag_named_scholars_as_adjunct_mentors.py",
}


def _catalog_files() -> set[str]:
    return {item.file for item in MIGRATION_CATALOG}


def _print_list() -> None:
    print("Catalog scripts:")
    for item in MIGRATION_CATALOG:
        print(f"- {item.file} [{item.status}]")


def _resolve_script_path(file_name: str) -> Path:
    rel = Path(file_name)
    if rel.is_absolute():
        raise ValueError("Use relative file path from scripts/migration")
    path = (ROOT_DIR / "scripts" / "migration" / rel).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Script not found: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run migration script from catalog.")
    parser.add_argument("--list", action="store_true", help="List scripts in catalog and exit")
    parser.add_argument("--run", type=str, help="Catalog file path to execute")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Pass --dry-run when supported")
    mode.add_argument("--apply", action="store_true", help="Pass --apply")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Extra args after --")
    args = parser.parse_args()

    if args.list:
        _print_list()
        return

    if not args.run:
        parser.error("either --list or --run is required")

    catalog_files = _catalog_files()
    if args.run not in catalog_files:
        parser.error(f"script not in catalog: {args.run}")

    script_path = _resolve_script_path(args.run)

    cmd = [sys.executable, str(script_path)]
    if args.apply:
        cmd.append("--apply")
    elif args.dry_run:
        if args.run in _SUPPORTS_DRY_RUN:
            cmd.append("--dry-run")
        else:
            print(f"[info] {args.run} does not declare --dry-run; using default non-apply mode.")

    extra = list(args.args)
    if extra and extra[0] == "--":
        extra = extra[1:]
    cmd.extend(extra)

    print("[run]", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT_DIR))


if __name__ == "__main__":
    main()
