from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg


async def reliability(
    pool: asyncpg.Pool, org_id: UUID,
    frm: datetime | None, to: datetime | None, group_by: str,
) -> dict:
    group_col = {"vendor": "vendor", "model": "model"}.get(group_by, "vendor")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
              COALESCE(c.{group_col}, 'unknown') AS name,
              COUNT(DISTINCT c.cp_id) AS charger_count,
              COALESCE(AVG(EXTRACT(EPOCH FROM (i.resolved_at - i.detected_at)) / 3600.0)
                       FILTER (WHERE i.resolved_at IS NOT NULL), 0) AS mttr_hours,
              COALESCE(AVG(c.health_score), 100) AS avg_health
            FROM chargers c
            LEFT JOIN incidents i ON i.cp_id = c.cp_id
              AND ($2::timestamptz IS NULL OR i.detected_at >= $2)
              AND ($3::timestamptz IS NULL OR i.detected_at <= $3)
            WHERE c.org_id = $1
            GROUP BY name
            ORDER BY charger_count DESC
            """,
            org_id, frm, to,
        )
    return {
        "groups": [
            {
                "name": r["name"],
                "charger_count": r["charger_count"],
                "avg_health": float(r["avg_health"]),
                "mttr_hours": float(r["mttr_hours"]),
                "mtbf_hours": None,
            }
            for r in rows
        ]
    }


async def vendor_comparison(pool: asyncpg.Pool, org_id: UUID) -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              COALESCE(c.vendor, 'unknown') AS vendor,
              COALESCE(c.model, 'unknown')  AS model,
              COUNT(*) AS charger_count,
              AVG(c.health_score) AS avg_health,
              COALESCE(
                SUM(CASE WHEN i.id IS NOT NULL THEN 1 ELSE 0 END)::float
                / GREATEST(COUNT(*), 1), 0
              ) AS incident_rate
            FROM chargers c
            LEFT JOIN incidents i ON i.cp_id = c.cp_id
            WHERE c.org_id = $1
            GROUP BY vendor, model
            ORDER BY charger_count DESC
            """,
            org_id,
        )
    return {
        "vendors": [
            {
                "vendor": r["vendor"],
                "model": r["model"],
                "charger_count": r["charger_count"],
                "avg_health": float(r["avg_health"]),
                "avg_uptime": None,
                "incident_rate": float(r["incident_rate"]),
            }
            for r in rows
        ]
    }


async def predictions(pool: asyncpg.Pool, org_id: UUID) -> dict:
    """Until the survival model trains (Week 4+), surface chargers with the
    lowest current health scores as the 'most likely to fail soon' set."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cp_id, display_name, health_score
            FROM chargers
            WHERE org_id = $1
            ORDER BY health_score ASC
            LIMIT 20
            """,
            org_id,
        )
    return {
        "predictions": [
            {
                "cp_id": r["cp_id"],
                "display_name": r["display_name"],
                "predicted_failure_type": None,
                "confidence": None,
                "estimated_hours_to_failure": None,
                "health_score": float(r["health_score"]),
            }
            for r in rows
        ]
    }
