#!/usr/bin/env python3
"""Unified entrypoint for scholar institution cleanup migrations.

Default scope is `global` which consolidates prior behaviors and is the
recommended option for scholar sidebar institution quality fixes.

Usage:
  .venv/bin/python scripts/migration/fix_scholar_institutions.py
  .venv/bin/python scripts/migration/fix_scholar_institutions.py --apply
  .venv/bin/python scripts/migration/fix_scholar_institutions.py --scope domestic --apply
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

# Ensure repo root is importable when executed as a file path.
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ScopeRunner = Callable[..., Awaitable[None]]

_SCOPE_TO_MODULE: dict[str, tuple[str, str]] = {
    "global": ("scripts.migration.fix_scholar_institutions_region_and_merge", "main"),
    "domestic": ("scripts.migration.archive.legacy.fix_scholar_institutions_domestic_cleanup", "main"),
    "full": ("scripts.migration.archive.legacy.fix_scholar_institutions_full", "main"),
}


def _resolve_runner(scope: str) -> ScopeRunner:
    module_name, func_name = _SCOPE_TO_MODULE[scope]
    module = importlib.import_module(module_name)
    runner = getattr(module, func_name)
    return runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scholar institution cleanup migrations.")
    parser.add_argument(
        "--scope",
        choices=tuple(_SCOPE_TO_MODULE.keys()),
        default="global",
        help="Cleanup scope: global (recommended), domestic, or full(legacy).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database. Without this flag runs in dry-run mode.",
    )
    parser.add_argument(
        "--skip-org-row-conversion",
        action="store_true",
        help="Global scope only: skip converting malformed organization rows into departments.",
    )
    args = parser.parse_args()

    if args.scope != "global":
        print(
            "[warn] non-global scope selected. Prefer `--scope global` for consolidated behavior."
        )

    runner = _resolve_runner(args.scope)
    kwargs: dict[str, object] = {"apply": args.apply}
    if args.scope == "global":
        kwargs["convert_org_rows"] = not args.skip_org_row_conversion
    asyncio.run(runner(**kwargs))


if __name__ == "__main__":
    main()
