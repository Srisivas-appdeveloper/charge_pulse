from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.analytics import service
from app.auth.permissions import require_role
from app.dependencies import CurrentUserCtx, DBPool

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/reliability")
async def reliability(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    group_by: str = "vendor",
):
    return await service.reliability(pool, user.org_id, frm, to, group_by)


@router.get("/vendor-comparison")
async def vendor_comparison(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
):
    return await service.vendor_comparison(pool, user.org_id)


@router.get("/predictions")
async def predictions(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
):
    return await service.predictions(pool, user.org_id)
