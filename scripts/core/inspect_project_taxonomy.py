#!/usr/bin/env python3
"""Inspect project taxonomy tree and print summary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.core.project_taxonomy_service import get_taxonomy_tree


def main() -> int:
    tree = get_taxonomy_tree()
    if tree.total_l1 < 3 or tree.total_l2 < 7:
        print(
            f"FAIL: unexpected taxonomy size total_l1={tree.total_l1} total_l2={tree.total_l2}",
            file=sys.stderr,
        )
        return 1

    if not any(item.name == "教育培养" for item in tree.items):
        print("FAIL: taxonomy missing '教育培养' root category", file=sys.stderr)
        return 1

    payload = {
        "total_l1": tree.total_l1,
        "total_l2": tree.total_l2,
        "roots": [item.name for item in tree.items],
    }
    print("PASS: project taxonomy loaded")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
