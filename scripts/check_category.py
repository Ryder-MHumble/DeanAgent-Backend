#!/usr/bin/env python3
"""Check if category column exists and has data."""
import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

async def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL or SUPABASE_KEY not set")
        return

    client = create_client(url, key)

    # Check if category column exists by querying events
    print("Checking events table...")
    res = client.table("events").select("id,category,series,event_type").limit(5).execute()

    if res.data:
        print(f"\nFound {len(res.data)} events:")
        for r in res.data:
            cat = r.get("category", "NULL")
            series = r.get("series", "")
            etype = r.get("event_type", "")
            print(f"  - category: '{cat}' | series: '{series}' | type: '{etype}'")
    else:
        print("No events found")

    # Check event_taxonomy table
    print("\nChecking event_taxonomy table...")
    try:
        tax_res = client.table("event_taxonomy").select("*").limit(5).execute()
        print(f"Found {len(tax_res.data)} taxonomy nodes")
        for t in tax_res.data:
            print(f"  - L{t['level']}: {t['name']} (parent: {t.get('parent_id', 'NULL')[:8] if t.get('parent_id') else 'NULL'})")
    except Exception as e:
        print(f"ERROR querying event_taxonomy: {e}")

if __name__ == "__main__":
    asyncio.run(main())
