"""FastAPI dependency injection.

Multi-tenancy: every request resolves `CurrentUser` from the bearer token, and
every downstream query is scoped to `org_id`. There is no way to query across
organisations from the API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.security import decode_token
from app.db.session import get_pool

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)


@dataclass(frozen=True)
class CurrentUserCtx:
    user_id: UUID
    org_id: UUID
    role: str


async def _get_pool() -> asyncpg.Pool:
    return await get_pool()


async def _get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUserCtx:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    try:
        return CurrentUserCtx(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            role=payload["role"],
        )
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed token")


DBPool = Annotated[asyncpg.Pool, Depends(_get_pool)]
CurrentUser = Annotated[CurrentUserCtx, Depends(_get_current_user)]
