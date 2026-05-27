from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.auth.permissions import require_role
from app.dependencies import CurrentUserCtx, DBPool
from app.fleet import service

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/overview")
async def overview(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
):
    return await service.overview(pool, user.org_id)


@router.get("/map")
async def map_data(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
):
    return await service.map_data(pool, user.org_id)


@router.get("/uptime")
async def uptime(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    granularity: str = "daily",
):
    return await service.uptime(pool, user.org_id, frm, to, granularity)
