#!/usr/bin/env python3
"""
Initialize event_taxonomy table from YAML configuration.

This script reads config/event_taxonomy.yaml and populates the event_taxonomy table
in the database with the predefined category structure.

Usage:
    python scripts/init_event_taxonomy.py --dry-run  # Preview changes
    python scripts/init_event_taxonomy.py            # Apply changes
"""

import argparse
import asyncio
import os
import uuid
from pathlib import Path

import yaml
from dotenv import load_dotenv

from app.db.client import init_client, get_client

load_dotenv()

TAXONOMY_CONFIG = Path(__file__).parent.parent / "config" / "event_taxonomy.yaml"


async def init_taxonomy(dry_run: bool = True):
    """Initialize event_taxonomy table from YAML config."""
    await init_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    client = get_client()

    # Load YAML config
    if not TAXONOMY_CONFIG.exists():
        print(f"❌ Config file not found: {TAXONOMY_CONFIG}")
        return

    with open(TAXONOMY_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    taxonomy = config.get("taxonomy", [])
    if not taxonomy:
        print("❌ No taxonomy data found in config")
        return

    print(f"📖 Loaded taxonomy config from {TAXONOMY_CONFIG}")
    print(f"Found {len(taxonomy)} L1 categories\n")

    # Check existing data
    result = await client.table("event_taxonomy").select("id, name, level").execute()
    existing = result.data or []
    print(f"Current database has {len(existing)} taxonomy nodes")

    if existing and not dry_run:
        print("\n⚠️  Database already has taxonomy data. Clear it first? (y/N): ", end="")
        response = input().strip().lower()
        if response != "y":
            print("Aborted.")
            return

        print("🗑️  Clearing existing taxonomy data...")
        await client.table("event_taxonomy").delete().neq("id", "").execute()

    # Build insert list
    nodes_to_insert = []

    for l1 in taxonomy:
        l1_id = str(uuid.uuid4())
        nodes_to_insert.append(
            {
                "id": l1_id,
                "level": 1,
                "name": l1["name"],
                "parent_id": None,
                "sort_order": l1.get("sort_order", 0),
            }
        )

        for l2 in l1.get("children", []):
            l2_id = str(uuid.uuid4())
            nodes_to_insert.append(
                {
                    "id": l2_id,
                    "level": 2,
                    "name": l2["name"],
                    "parent_id": l1_id,
                    "sort_order": l2.get("sort_order", 0),
                }
            )

            for l3 in l2.get("children", []):
                l3_id = str(uuid.uuid4())
                nodes_to_insert.append(
                    {
                        "id": l3_id,
                        "level": 3,
                        "name": l3["name"],
                        "parent_id": l2_id,
                        "sort_order": l3.get("sort_order", 0),
                    }
                )

    print(f"\n📋 Prepared {len(nodes_to_insert)} nodes to insert:")
    for node in nodes_to_insert:
        indent = "  " * (node["level"] - 1)
        print(f"{indent}L{node['level']}: {node['name']}")

    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes applied")
        print("Run without --dry-run to apply changes")
        return

    # Insert nodes
    print("\n🚀 Inserting nodes into database...")
    await client.table("event_taxonomy").insert(nodes_to_insert).execute()

    print(f"\n✅ Successfully initialized {len(nodes_to_insert)} taxonomy nodes")

    # Verify
    result = await client.table("event_taxonomy").select("level").execute()
    by_level = {}
    for row in result.data:
        level = row["level"]
        by_level[level] = by_level.get(level, 0) + 1

    print("\n📊 Final taxonomy structure:")
    for level in sorted(by_level.keys()):
        print(f"  L{level}: {by_level[level]} nodes")


def main():
    parser = argparse.ArgumentParser(description="Initialize event taxonomy from YAML")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    args = parser.parse_args()

    asyncio.run(init_taxonomy(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
