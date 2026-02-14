from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source


async def list_sources(db: AsyncSession, dimension: str | None = None) -> list[Source]:
    query = select(Source).order_by(Source.dimension, Source.priority)
    if dimension:
        query = query.where(Source.dimension == dimension)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_source(db: AsyncSession, source_id: str) -> Source | None:
    result = await db.execute(select(Source).where(Source.id == source_id))
    return result.scalar_one_or_none()


async def update_source(db: AsyncSession, source_id: str, is_enabled: bool) -> Source | None:
    await db.execute(
        update(Source).where(Source.id == source_id).values(is_enabled=is_enabled)
    )
    await db.commit()
    return await get_source(db, source_id)
