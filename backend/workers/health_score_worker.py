"""Health score worker (Section 8.5).

Recomputes chargers.health_score every hour using a weighted mix of:
  - anomaly frequency (last 7d)            weight 0.3
  - session completion rate (last 7d)      weight 0.2
  - available + charging uptime (last 7d)  weight 0.3
  - heartbeat stability (last 7d)          weight 0.2
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from app.config import get_settings
from app.db.session import create_asyncpg_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.health_score")

CHECK_INTERVAL_SEC = 3600  # hourly


async def compute_health(conn: asyncpg.Connection, cp_id: str) -> float:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # anomaly frequency
    row = await conn.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE is_anomaly) AS anomalies,
          NULLIF(COUNT(*), 0) AS total
        FROM feature_vectors
        WHERE cp_id = $1 AND time >= $2
        """,
        cp_id, cutoff,
    )
    if row["total"]:
        anomaly_frac = (row["anomalies"] or 0) / row["total"]
        anomaly_component = (1.0 - anomaly_frac) * 100
    else:
        anomaly_component = 100.0

    # session completion
    row = await conn.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE stop_reason = 'EVDisconnected') AS ok,
          COUNT(*) FILTER (WHERE stop_reason IS NOT NULL) AS total
        FROM charger_sessions
        WHERE cp_id = $1 AND started_at >= $2
        """,
        cp_id, cutoff,
    )
    completion = (row["ok"] / row["total"]) if row["total"] else 1.0
    completion_component = completion * 100

    # uptime (available + charging proxy via available_count vs faulted_count)
    row = await conn.fetchrow(
        """
        SELECT
          COALESCE(SUM(available_count), 0) AS avail,
          COALESCE(SUM(faulted_count), 0)   AS faulted
        FROM charger_uptime_hourly
        WHERE cp_id = $1 AND bucket >= $2
        """,
        cp_id, cutoff,
    )
    denom = (row["avail"] or 0) + (row["faulted"] or 0)
    uptime_component = ((row["avail"] / denom) if denom else 1.0) * 100

    # heartbeat stability — use feature[20] (heartbeat_gap_std_sec); lower is better
    row = await conn.fetchrow(
        """
        SELECT AVG(features[21]) AS gap_std, AVG(features[20]) AS gap_max
        FROM feature_vectors
        WHERE cp_id = $1 AND time >= $2
        """,
        cp_id, cutoff,
    )
    gap_std = row["gap_std"] or 0.0
    hb_component = max(0.0, 100.0 - min(100.0, gap_std))

    score = (
        0.3 * anomaly_component
        + 0.2 * completion_component
        + 0.3 * uptime_component
        + 0.2 * hb_component
    )
    return max(0.0, min(100.0, score))


async def run_once(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        chargers = await conn.fetch("SELECT cp_id FROM chargers")
        for c in chargers:
            try:
                score = await compute_health(conn, c["cp_id"])
                await conn.execute(
                    "UPDATE chargers SET health_score = $1, updated_at = now() WHERE cp_id = $2",
                    score, c["cp_id"],
                )
                log.info("health_score cp=%s score=%.1f", c["cp_id"], score)
            except Exception:
                log.exception("health compute failed cp=%s", c["cp_id"])


async def main() -> None:
    get_settings()  # warm settings
    pool = await create_asyncpg_pool()
    log.info("Health score worker started (interval=%ds)", CHECK_INTERVAL_SEC)
    try:
        # Run once on boot so the first cycle isn't an hour away.
        await run_once(pool)
        while True:
            await asyncio.sleep(CHECK_INTERVAL_SEC)
            await run_once(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
