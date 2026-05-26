from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg


async def overview(pool: asyncpg.Pool, org_id: UUID) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              count(*)                                    AS total_chargers,
              count(*) FILTER (WHERE status = 'online')   AS online,
              count(*) FILTER (WHERE status = 'offline')  AS offline,
              count(*) FILTER (WHERE status = 'faulted')  AS faulted,
              COALESCE(AVG(health_score), 100)            AS avg_health_score
            FROM chargers WHERE org_id = $1
            """,
            org_id,
        )
        incidents = await conn.fetchrow(
            """
            SELECT
              count(*) FILTER (WHERE resolved_at IS NULL) AS open_incidents,
              count(*) FILTER (WHERE resolved_at IS NULL
                               AND severity = 'critical') AS critical_incidents
            FROM incidents WHERE org_id = $1
            """,
            org_id,
        )
        today = datetime.now(timezone.utc).date()
        sessions = await conn.fetchrow(
            """
            SELECT
              count(*) AS sessions_today,
              COALESCE(SUM(energy_kwh), 0) AS energy_today_kwh
            FROM charger_sessions
            WHERE org_id = $1 AND started_at >= $2
            """,
            org_id, datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
        )
        uptime_7d = await conn.fetchval(
            """
            SELECT COALESCE(AVG(available_count::float
              / NULLIF(available_count + faulted_count, 0)), 1.0) * 100
            FROM charger_uptime_hourly
            WHERE org_id = $1 AND bucket >= $2
            """,
            org_id, datetime.now(timezone.utc) - timedelta(days=7),
        ) or 100.0
    return {
        "total_chargers": row["total_chargers"],
        "online": row["online"],
        "offline": row["offline"],
        "faulted": row["faulted"],
        "avg_health_score": float(row["avg_health_score"] or 100),
        "avg_uptime_7d": float(uptime_7d),
        "open_incidents": incidents["open_incidents"],
        "critical_incidents": incidents["critical_incidents"],
        "sessions_today": sessions["sessions_today"],
        "energy_today_kwh": float(sessions["energy_today_kwh"] or 0),
    }


async def map_data(pool: asyncpg.Pool, org_id: UUID) -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cp_id, display_name, status, health_score,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lng,
                   address, city
            FROM chargers WHERE org_id = $1
            """,
            org_id,
        )
    return {
        "chargers": [
            {
                "cp_id": r["cp_id"],
                "display_name": r["display_name"],
                "status": r["status"],
                "health_score": float(r["health_score"]),
                "lat": r["lat"],
                "lng": r["lng"],
                "address": r["address"],
                "city": r["city"],
            }
            for r in rows
        ]
    }


async def uptime(
    pool: asyncpg.Pool, org_id: UUID,
    frm: datetime | None, to: datetime | None, granularity: str,
) -> dict:
    bucket = "1 day" if granularity == "daily" else "1 hour"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT time_bucket('{bucket}', bucket) AS t,
                   COUNT(DISTINCT cp_id) AS chargers_online,
                   COALESCE(AVG(available_count::float
                     / NULLIF(available_count + faulted_count, 0)), 1.0) AS uptime
            FROM charger_uptime_hourly
            WHERE org_id = $1
              AND ($2::timestamptz IS NULL OR bucket >= $2)
              AND ($3::timestamptz IS NULL OR bucket <= $3)
            GROUP BY t ORDER BY t
            """,
            org_id, frm, to,
        )
    return {
        "timeline": [
            {
                "date": r["t"].isoformat(),
                "uptime_pct": float(r["uptime"]) * 100,
                "chargers_online": r["chargers_online"],
            }
            for r in rows
        ]
    }
