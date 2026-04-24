"""Global asyncpg connection pool for Supabase."""
from __future__ import annotations

import asyncio

import asyncpg

_pools: dict[int, asyncpg.Pool] = {}
_connect_kwargs: dict | None = None
_primary_loop_id: int | None = None


def _normalize_args(args):
    normalized = []
    for value in args:
        if isinstance(value, (dict, list)):
            import json

            normalized.append(json.dumps(value))
        else:
            normalized.append(value)
    return tuple(normalized)


class _LoopAwarePoolProxy:
    async def _resolve_pool(self) -> asyncpg.Pool:
        loop = asyncio.get_running_loop()
        pool = _pools.get(id(loop))
        if pool is not None:
            return pool
        if _connect_kwargs is None:
            raise RuntimeError("DB pool not initialized. Call init_pool() first.")
        pool = await asyncpg.create_pool(**_connect_kwargs)
        _pools[id(loop)] = pool
        return pool

    async def execute(self, query: str, *args, timeout=None) -> str:
        pool = await self._resolve_pool()
        return await pool.execute(query, *_normalize_args(args), timeout=timeout)

    async def fetch(self, query: str, *args, timeout=None):
        pool = await self._resolve_pool()
        return await pool.fetch(query, *_normalize_args(args), timeout=timeout)

    async def fetchrow(self, query: str, *args, timeout=None):
        pool = await self._resolve_pool()
        return await pool.fetchrow(query, *_normalize_args(args), timeout=timeout)

    async def fetchval(self, query: str, *args, timeout=None):
        pool = await self._resolve_pool()
        return await pool.fetchval(query, *_normalize_args(args), timeout=timeout)


_proxy = _LoopAwarePoolProxy()


async def init_pool(
    dsn: str | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    **kwargs,
) -> None:
    """Initialize the global connection pool. Call once at app startup.

    Two modes:
    - Keyword params (recommended): init_pool(host=..., port=..., user=..., password=..., database=...)
      No URL encoding needed — safe for passwords with special characters.
    - DSN string: init_pool(dsn="postgresql+asyncpg://user:pass@host:port/db")
      Passwords with '@' or ']' must be URL-encoded (%40, %5D).
    """
    global _connect_kwargs, _primary_loop_id
    loop = asyncio.get_running_loop()
    if id(loop) in _pools:
        return

    if host:
        # Keyword-param mode: pass directly to asyncpg (no URL parsing)
        connect_kwargs: dict = {
            "host": host,
            "port": port or 6543,
            "user": user or "postgres",
            "password": password or "",
            "database": database or "postgres",
            "min_size": 2,
            "max_size": 10,
            **kwargs,
        }
    else:
        if not dsn:
            raise ValueError("Either dsn or host must be provided")
        # DSN mode: strip ORM prefix, parse manually (handles @ in passwords)
        from urllib.parse import unquote  # noqa: PLC0415

        clean_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace(
            "postgresql+psycopg2://", "postgresql://"
        )
        scheme_end = clean_dsn.index("://") + 3
        rest = clean_dsn[scheme_end:]

        last_at = rest.rfind("@")
        credentials = rest[:last_at]
        host_part = rest[last_at + 1:]

        first_colon = credentials.index(":")
        _user = unquote(credentials[:first_colon])
        _password = unquote(credentials[first_colon + 1:])

        host_db, _, _database = host_part.partition("/")
        _host, _, port_str = host_db.partition(":")
        _port = int(port_str) if port_str else 5432

        connect_kwargs = {
            "host": _host,
            "port": _port,
            "user": _user,
            "password": _password,
            "database": _database or "postgres",
            "min_size": 2,
            "max_size": 10,
            **kwargs,
        }

    _connect_kwargs = connect_kwargs
    if _primary_loop_id is None:
        _primary_loop_id = id(loop)
    pool = await asyncpg.create_pool(**connect_kwargs)
    _pools[id(loop)] = pool


async def close_pool() -> None:
    """Close the connection pool. Call at app shutdown."""
    global _pools, _primary_loop_id
    for pool in list(_pools.values()):
        try:
            if getattr(pool, "_loop", None) is not None and pool._loop.is_closed():
                continue
            await pool.close()
        except RuntimeError:
            continue
    _pools = {}
    _primary_loop_id = None


def get_pool() -> asyncpg.Pool:
    """Get the active pool. Raises RuntimeError if not initialized."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if not _pools:
            raise RuntimeError("DB pool not initialized. Call init_pool() first.")
        return next(iter(_pools.values()))
    pool = _pools.get(id(loop))
    if pool is not None and id(loop) == _primary_loop_id:
        return pool
    if not _pools and _connect_kwargs is None:
        raise RuntimeError("DB pool not initialized. Call init_pool() first.")
    return _proxy  # type: ignore[return-value]


async def execute(query: str, *args) -> str:
    """Execute a query (INSERT/UPDATE/DELETE) and return status."""
    return await get_pool().execute(query, *args)


async def fetch(query: str, *args) -> list[asyncpg.Record]:
    """Fetch multiple rows."""
    return await get_pool().fetch(query, *args)


async def fetchrow(query: str, *args) -> asyncpg.Record | None:
    """Fetch a single row."""
    return await get_pool().fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Fetch a single value."""
    return await get_pool().fetchval(query, *args)
