"""Seed sources table from YAML config files."""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import async_session_factory, engine
from app.models import Base, Source
from app.scheduler.manager import load_all_source_configs


async def seed():
    """Load all YAML configs and upsert into the sources table."""
    configs = load_all_source_configs()
    print(f"Loaded {len(configs)} source configs")

    async with async_session_factory() as session:
        for config in configs:
            source_id = config["id"]
            existing = await session.get(Source, source_id)

            if existing:
                # Update existing source config
                existing.name = config.get("name", source_id)
                existing.url = config.get("url", "")
                existing.dimension = config.get("dimension", "")
                existing.crawl_method = config.get("crawl_method", "static")
                existing.schedule = config.get("schedule", "daily")
                existing.is_enabled = config.get("is_enabled", True)
                existing.priority = config.get("priority", 2)
                existing.config_json = config
                print(f"  Updated: {source_id}")
            else:
                # Insert new source
                source = Source(
                    id=source_id,
                    name=config.get("name", source_id),
                    url=config.get("url", ""),
                    dimension=config.get("dimension", ""),
                    crawl_method=config.get("crawl_method", "static"),
                    schedule=config.get("schedule", "daily"),
                    is_enabled=config.get("is_enabled", True),
                    priority=config.get("priority", 2),
                    config_json=config,
                )
                session.add(source)
                print(f"  Created: {source_id}")

        await session.commit()
    print("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
