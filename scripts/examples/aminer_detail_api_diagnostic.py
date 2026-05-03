#!/usr/bin/env python3
"""AMiner scholar-detail API diagnostic.

Usage:
  python scripts/examples/aminer_detail_api_diagnostic.py --scholar-id <id> [--force-refresh]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.external.aminer import get_scholar_detail


async def _run(scholar_id: str, force_refresh: bool) -> int:
    try:
        detail = await get_scholar_detail(scholar_id, force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: AMiner detail request failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "id": detail.id,
        "name": detail.name,
        "name_zh": detail.name_zh,
        "org": detail.org,
        "position": detail.position,
        "h_index": detail.h_index,
        "citations": detail.citations,
        "has_raw_data": bool(detail.raw_data),
    }
    print("PASS: AMiner detail API reachable")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose AMiner detail API")
    parser.add_argument("--scholar-id", required=True, help="AMiner scholar id")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="force upstream refresh",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.scholar_id, args.force_refresh))


if __name__ == "__main__":
    raise SystemExit(main())
