from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.alerts import schemas


_COLS = "id, channel, endpoint, label, severity_min, is_active, created_at"


async def list_configs(pool: asyncpg.Pool, org_id: UUID) -> schemas.AlertConfigListResponse:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {_COLS} FROM alert_configs WHERE org_id = $1 ORDER BY created_at",
            org_id,
        )
    return schemas.AlertConfigListResponse(
        configs=[schemas.AlertConfigOut(**dict(r)) for r in rows]
    )


async def create_config(
    pool: asyncpg.Pool, org_id: UUID, req: schemas.AlertConfigCreate,
) -> schemas.AlertConfigOut:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO alert_configs (org_id, channel, endpoint, label, severity_min)
            VALUES ($1, $2, $3, $4, $5) RETURNING {_COLS}
            """,
            org_id, req.channel, req.endpoint, req.label, req.severity_min,
        )
    return schemas.AlertConfigOut(**dict(row))


async def update_config(
    pool: asyncpg.Pool, org_id: UUID, config_id: UUID, req: schemas.AlertConfigUpdate,
) -> schemas.AlertConfigOut:
    updates = []
    params: list = []
    for field in ("endpoint", "label", "severity_min", "is_active"):
        value = getattr(req, field)
        if value is not None:
            params.append(value); updates.append(f"{field} = ${len(params)}")
    if not updates:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLS} FROM alert_configs WHERE id=$1 AND org_id=$2",
                config_id, org_id,
            )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "config not found")
        return schemas.AlertConfigOut(**dict(row))

    params.extend([config_id, org_id])
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE alert_configs SET {', '.join(updates)} "
            f"WHERE id = ${len(params)-1} AND org_id = ${len(params)} "
            f"RETURNING {_COLS}",
            *params,
        )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "config not found")
    return schemas.AlertConfigOut(**dict(row))


async def delete_config(pool: asyncpg.Pool, org_id: UUID, config_id: UUID) -> None:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM alert_configs WHERE id = $1 AND org_id = $2",
            config_id, org_id,
        )
    if result.endswith("0"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "config not found")
