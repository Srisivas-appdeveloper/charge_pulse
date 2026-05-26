"""Feature worker.

Every FEATURE_WINDOW_MINUTES, for every charger that has had any activity
in the past window, query the raw events + sessions and materialize a
24-feature vector into the `feature_vectors` hypertable.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import redis.asyncio as redis_async

from app.config import get_settings
from app.db.session import create_asyncpg_pool
from ml import features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.feature_worker")


async def compute_window(
    pool: asyncpg.Pool, redis: redis_async.Redis,
    cp_id: str, org_id, window_start: datetime, window_end: datetime,
) -> None:
    async with pool.acquire() as conn:
        event_rows = await conn.fetch(
            """
            SELECT time, event_type, connector_id, payload
            FROM ocpp_events
            WHERE cp_id = $1 AND time >= $2 AND time < $3
            ORDER BY time
            """,
            cp_id, window_start, window_end,
        )
        session_rows = await conn.fetch(
            """
            SELECT started_at, stopped_at, energy_kwh, duration_min, stop_reason
            FROM charger_sessions
            WHERE cp_id = $1 AND started_at >= $2 AND started_at < $3
            """,
            cp_id, window_start, window_end,
        )

    if not event_rows and not session_rows:
        return

    fv = features.extract(
        cp_id=cp_id,
        window_start=window_start,
        window_end=window_end,
        events=[dict(r) for r in event_rows],
        sessions=[dict(r) for r in session_rows],
    )

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO feature_vectors (time, cp_id, org_id, features)
            VALUES ($1, $2, $3, $4)
            """,
            window_end, cp_id, org_id, list(fv.values),
        )

    payload = {
        "cp_id": cp_id,
        "org_id": str(org_id),
        "window_end": window_end.isoformat(),
        "features": json.dumps(features.to_dict(fv)),
    }
    await redis.xadd(f"stream:features:{cp_id}", payload, maxlen=10_000, approximate=True)
    log.info("Features stored cp=%s window_end=%s", cp_id, window_end.isoformat())


async def run_once(
    pool: asyncpg.Pool, redis: redis_async.Redis, window_minutes: int,
) -> None:
    now = datetime.now(timezone.utc)
    # Round down to the previous window boundary.
    window_end = now.replace(second=0, microsecond=0) - timedelta(
        minutes=now.minute % window_minutes
    )
    window_start = window_end - timedelta(minutes=window_minutes)

    async with pool.acquire() as conn:
        active = await conn.fetch(
            """
            SELECT DISTINCT cp_id, org_id FROM ocpp_events
            WHERE time >= $1 AND time < $2
            """,
            window_start, window_end,
        )
    if not active:
        log.info("No active chargers in window %s..%s", window_start, window_end)
        return

    for row in active:
        # Skip if already computed for this window.
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT 1 FROM feature_vectors WHERE cp_id=$1 AND time=$2",
                row["cp_id"], window_end,
            )
        if existing:
            continue
        try:
            await compute_window(
                pool, redis, row["cp_id"], row["org_id"], window_start, window_end,
            )
        except Exception:
            log.exception("Feature compute failed cp=%s", row["cp_id"])


async def main() -> None:
    settings = get_settings()
    pool = await create_asyncpg_pool()
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    window = settings.feature_window_minutes
    interval = max(30, window * 60 // 3)  # check several times per window
    log.info("Feature worker: window=%dm, check_every=%ds", window, interval)
    try:
        while True:
            try:
                await run_once(pool, redis, window)
            except Exception:
                log.exception("run_once failed")
            await asyncio.sleep(interval)
    finally:
        await redis.aclose()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
