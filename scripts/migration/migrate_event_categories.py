#!/usr/bin/env python3
"""
Migrate existing events to the new category structure.

Current situation:
- All events have category='科研学术' and series='' (empty)
- According to the taxonomy, they should be '科研学术 - XAI智汇讲坛'

Usage:
    python scripts/migrate_event_categories.py --dry-run  # Preview changes
    python scripts/migrate_event_categories.py            # Apply changes
"""

import argparse
import asyncio
import os
from dotenv import load_dotenv

from app.db.client import init_client, get_client

load_dotenv()


async def migrate_events(dry_run: bool = True):
    """Migrate existing events to new category structure."""
    await init_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    client = get_client()

    # Fetch all events
    result = await client.table("events").select("id, title, category, series").execute()
    events = result.data

    print(f"Found {len(events)} events in database\n")

    # Define migration rules
    # All current events should be: 科研学术 - XAI智汇讲坛
    updates = []
    for event in events:
        event_id = event["id"]
        current_category = event.get("category", "")
        current_series = event.get("series", "")

        # Check if migration is needed
        if current_category == "科研学术" and not current_series:
            updates.append(
                {
                    "id": event_id,
                    "title": event["title"][:60],
                    "old_category": current_category,
                    "old_series": current_series or "(empty)",
                    "new_category": "科研学术",
                    "new_series": "XAI智汇讲坛",
                }
            )

    if not updates:
        print("✅ No events need migration. All events are already properly categorized.")
        return

    print(f"📋 Found {len(updates)} events to migrate:\n")
    for i, update in enumerate(updates, 1):
        print(f"{i}. {update['title']}...")
        print(f"   Current: {update['old_category']} - {update['old_series']}")
        print(f"   New:     {update['new_category']} - {update['new_series']}\n")

    if dry_run:
        print("🔍 DRY RUN MODE - No changes applied")
        print("Run without --dry-run to apply changes")
        return

    # Apply updates
    print("🚀 Applying updates...")
    for update in updates:
        await client.table("events").update(
            {"category": update["new_category"], "series": update["new_series"]}
        ).eq("id", update["id"]).execute()

    print(f"\n✅ Successfully migrated {len(updates)} events")

    # Verify
    result = await client.table("events").select("category, series").execute()
    categories = {}
    for event in result.data:
        cat = event.get("category", "None")
        series = event.get("series", "None")
        key = f"{cat} - {series}"
        categories[key] = categories.get(key, 0) + 1

    print("\n📊 Final category distribution:")
    for key, count in sorted(categories.items()):
        print(f"  {key}: {count} events")


def main():
    parser = argparse.ArgumentParser(description="Migrate event categories")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    args = parser.parse_args()

    asyncio.run(migrate_events(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
