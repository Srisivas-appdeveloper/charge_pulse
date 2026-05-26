from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.incidents import schemas


_COLS = (
    "id, cp_id, severity, failure_type, anomaly_score, title, description, "
    "detected_at, acknowledged_at, resolved_at, resolution_notes, "
    "confirmed_failure_type, auto_detected"
)


async def list_incidents(
    pool: asyncpg.Pool, org_id: UUID,
    severity: str | None, failure_type: str | None, resolved: bool | None,
    cp_id: str | None, page: int, limit: int,
) -> schemas.IncidentListResponse:
    where = ["org_id = $1"]
    params: list = [org_id]
    if severity:
        params.append(severity); where.append(f"severity = ${len(params)}")
    if failure_type:
        params.append(failure_type); where.append(f"failure_type = ${len(params)}")
    if resolved is True:
        where.append("resolved_at IS NOT NULL")
    elif resolved is False:
        where.append("resolved_at IS NULL")
    if cp_id:
        params.append(cp_id); where.append(f"cp_id = ${len(params)}")
    where_sql = " AND ".join(where)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM incidents WHERE {where_sql}", *params,
        )
        params.extend([limit, (page - 1) * limit])
        rows = await conn.fetch(
            f"SELECT {_COLS} FROM incidents WHERE {where_sql} "
            f"ORDER BY detected_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params,
        )
    return schemas.IncidentListResponse(
        incidents=[schemas.IncidentOut(**dict(r)) for r in rows], total=total,
    )


async def get_incident(
    pool: asyncpg.Pool, org_id: UUID, incident_id: UUID,
) -> schemas.IncidentOut:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {_COLS} FROM incidents WHERE id = $1 AND org_id = $2",
            incident_id, org_id,
        )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
    return schemas.IncidentOut(**dict(row))


async def patch_incident(
    pool: asyncpg.Pool, org_id: UUID, incident_id: UUID,
    patch: schemas.IncidentPatch,
) -> schemas.IncidentOut:
    updates = []
    params: list = []
    for field in ("acknowledged_at", "resolved_at", "resolution_notes",
                  "confirmed_failure_type"):
        value = getattr(patch, field)
        if value is not None:
            params.append(value)
            updates.append(f"{field} = ${len(params)}")
    if not updates:
        return await get_incident(pool, org_id, incident_id)
    params.extend([incident_id, org_id])

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE incidents SET {', '.join(updates)} "
            f"WHERE id = ${len(params)-1} AND org_id = ${len(params)} "
            f"RETURNING {_COLS}",
            *params,
        )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
    return schemas.IncidentOut(**dict(row))
