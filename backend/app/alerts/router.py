from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.alerts import schemas, service
from app.auth.permissions import require_role
from app.dependencies import CurrentUserCtx, DBPool

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/config", response_model=schemas.AlertConfigListResponse)
async def list_configs(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.list_configs(pool, user.org_id)


@router.post("/config", response_model=schemas.AlertConfigOut, status_code=201)
async def create_config(
    req: schemas.AlertConfigCreate,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.create_config(pool, user.org_id, req)


@router.put("/config/{config_id}", response_model=schemas.AlertConfigOut)
async def update_config(
    config_id: UUID,
    req: schemas.AlertConfigUpdate,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.update_config(pool, user.org_id, config_id, req)


@router.delete("/config/{config_id}", status_code=204)
async def delete_config(
    config_id: UUID,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    await service.delete_config(pool, user.org_id, config_id)
