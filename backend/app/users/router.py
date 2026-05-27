"""FastAPI user management router."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth.permissions import require_role
from app.dependencies import DBPool, CurrentUserCtx
from . import schemas, service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[schemas.UserOut])
async def list_users(
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.list_users(pool, user.org_id)


@router.post("/invite", response_model=schemas.UserOut)
async def invite_user(
    req: schemas.InviteUserRequest,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.invite_user(pool, user.org_id, user.user_id, req.email, req.role)


@router.patch("/{user_id}", response_model=schemas.UserOut)
async def update_user_role(
    user_id: UUID,
    req: schemas.UserUpdateRoleRequest,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner", "admin")),
):
    return await service.update_user_role(pool, user.org_id, user_id, req.role)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    pool: DBPool,
    user: CurrentUserCtx = Depends(require_role("owner")),
):
    await service.remove_user(pool, user.org_id, user_id)
