from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import schemas, service
from app.dependencies import DBPool, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.AuthResponse)
async def register(req: schemas.RegisterRequest, pool: DBPool):
    return await service.register(pool, req)


@router.post("/login", response_model=schemas.AuthResponse)
async def login(req: schemas.LoginRequest, pool: DBPool):
    return await service.login(pool, req)


@router.get("/me", response_model=schemas.MeResponse)
async def me(pool: DBPool, user: CurrentUser):
    return await service.get_me(pool, user.user_id)
