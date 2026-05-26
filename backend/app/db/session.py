"""Async DB pool. Both the gateway and the API share this asyncpg pool."""
from __future__ import annotations

import asyncpg

from app.config import get_settings

settings = get_settings()

_pool: asyncpg.Pool | None = None


async def create_asyncpg_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        min_size=2,
        max_size=10,
    )


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await create_asyncpg_pool()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
