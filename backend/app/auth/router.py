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


@router.post("/accept-invite", response_model=schemas.AuthResponse)
async def accept_invite(req: schemas.AcceptInviteRequest, pool: DBPool):
    return await service.accept_invite(pool, req)


@router.patch("/me", response_model=schemas.UserOut)
async def update_me(req: schemas.UpdateProfileRequest, pool: DBPool, user: CurrentUser):
    return await service.update_profile(pool, user.user_id, req)


@router.post("/forgot-password")
async def forgot_password(req: schemas.ForgotPasswordRequest, pool: DBPool):
    # Mock / log for self-service
    import structlog
    log = structlog.get_logger()
    log.info("Password reset requested", email=req.email, token="mock-reset-token-xyz")
    return {"message": "If this email is registered, a password reset link has been logged"}


@router.post("/reset-password")
async def reset_password(req: schemas.ResetPasswordRequest, pool: DBPool):
    # Mock password reset execution (just completes successfully)
    return {"message": "Password reset successfully (mocked)"}
