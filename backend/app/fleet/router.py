from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.dependencies import CurrentUser, DBPool
from app.fleet import service

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/overview")
async def overview(pool: DBPool, user: CurrentUser):
    return await service.overview(pool, user.org_id)


@router.get("/map")
async def map_data(pool: DBPool, user: CurrentUser):
    return await service.map_data(pool, user.org_id)


@router.get("/uptime")
async def uptime(
    pool: DBPool, user: CurrentUser,
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    granularity: str = "daily",
):
    return await service.uptime(pool, user.org_id, frm, to, granularity)
