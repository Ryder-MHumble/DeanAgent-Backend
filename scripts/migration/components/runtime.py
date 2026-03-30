"""Shared runtime helpers for migration scripts."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.config import settings
from app.db.pool import close_pool, get_pool, init_pool

T = TypeVar("T")


async def init_postgres_pool_from_settings() -> None:
    """Initialize global postgres pool using project settings."""
    if settings.POSTGRES_DSN:
        await init_pool(dsn=settings.POSTGRES_DSN)
        return

    await init_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )


def get_postgres_pool():
    """Return initialized postgres pool."""
    return get_pool()


async def close_postgres_pool() -> None:
    """Close global postgres pool."""
    await close_pool()


async def run_with_postgres_pool(task: Callable[[], Awaitable[T]]) -> T:
    """Run async task with pooled DB lifecycle managed automatically."""
    await init_postgres_pool_from_settings()
    try:
        return await task()
    finally:
        await close_postgres_pool()
