from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

import redis.asyncio as redis_async

from app.auth.permissions import require_role
from app.chargers import schemas, service
from app.config import get_settings
from app.dependencies import CurrentUserCtx, DBPool

router = APIRouter(prefix="/chargers", tags=["chargers"])


@router.get("", response_model=schemas.ChargerListResponse)
async def list_chargers(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    status: str | None = None,
    health_below: float | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    return await service.list_chargers(
        pool,
        user.org_id,
        status_filter=status,
        health_below=health_below,
        page=page,
        limit=limit,
    )


@router.post("", response_model=schemas.ChargerOut, status_code=status.HTTP_201_CREATED)
async def create_charger(
    req: schemas.ChargerCreate,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.create_charger(pool, user.org_id, req)


@router.get("/{cp_id}", response_model=schemas.ChargerDetailResponse)
async def get_charger(
    cp_id: str,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
):
    return await service.get_charger(pool, user.org_id, cp_id)


@router.get("/{cp_id}/health", response_model=schemas.HealthResponse)
async def get_health(
    cp_id: str,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
):
    return await service.get_health(pool, user.org_id, cp_id, frm, to)


@router.get("/{cp_id}/telemetry", response_model=schemas.TelemetryResponse)
async def get_telemetry(
    cp_id: str,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    event_type: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
):
    return await service.get_telemetry(
        pool, user.org_id, cp_id, frm, to, event_type, limit
    )


@router.get("/{cp_id}/sessions", response_model=schemas.SessionListResponse)
async def get_sessions(
    cp_id: str,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    return await service.get_sessions(pool, user.org_id, cp_id, frm, to, page, limit)


@router.post("/bulk", response_model=schemas.BulkImportResponse)
async def bulk_import(
    req: schemas.BulkImportRequest,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.bulk_import(pool, user.org_id, req.chargers)


@router.post("/{cp_id}/command", response_model=schemas.CommandResponse)
async def send_command(
    cp_id: str,
    req: schemas.CommandRequest,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    # Validate charger belongs to caller's org before sending anything to the gateway.
    await service.get_charger(pool, user.org_id, cp_id)
    settings = get_settings()
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        return await service.send_command(redis, cp_id, req)
    finally:
        await redis.aclose()


@router.delete("/{cp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_charger(
    cp_id: str,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner")),
):
    await service.delete_charger(pool, user.org_id, cp_id)
