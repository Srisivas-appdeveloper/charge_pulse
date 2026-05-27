"""FastAPI superadmin router."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth.permissions import require_role
from app.dependencies import DBPool, CurrentUserCtx
from . import schemas, service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/orgs", status_code=status.HTTP_201_CREATED)
async def create_org(
    req: schemas.CreateOrgRequest,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("superadmin")),
):
    return await service.create_org(pool, req)


@router.get("/orgs", response_model=list[schemas.OrgAdminOut])
async def list_orgs(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("superadmin")),
):
    return await service.list_orgs(pool)


@router.get("/orgs/{org_id}", response_model=schemas.OrgDetailAdminOut)
async def get_org_detail(
    org_id: UUID,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("superadmin")),
):
    return await service.get_org_detail(pool, org_id)


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_org(
    org_id: UUID,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("superadmin")),
):
    await service.deactivate_org(pool, org_id)


@router.post("/impersonate/{org_id}")
async def impersonate(
    org_id: UUID,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("superadmin")),
):
    token = await service.impersonate(pool, user.user_id, org_id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/dashboard", response_model=schemas.AdminDashboardStats)
async def get_dashboard_stats(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("superadmin")),
):
    return await service.get_dashboard_stats(pool)
