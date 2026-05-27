from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth.permissions import require_role
from app.dependencies import CurrentUserCtx, DBPool
from app.incidents import schemas, service

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=schemas.IncidentListResponse)
async def list_incidents(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
    severity: str | None = None,
    failure_type: str | None = None,
    resolved: bool | None = None,
    cp_id: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    return await service.list_incidents(
        pool, user.org_id, severity, failure_type, resolved, cp_id, page, limit
    )


@router.get("/{incident_id}", response_model=schemas.IncidentOut)
async def get_incident(
    incident_id: UUID,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member", "viewer")),
):
    return await service.get_incident(pool, user.org_id, incident_id)


@router.patch("/{incident_id}", response_model=schemas.IncidentOut)
async def patch_incident(
    incident_id: UUID,
    patch: schemas.IncidentPatch,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin", "member")),
):
    return await service.patch_incident(pool, user.org_id, incident_id, patch)
