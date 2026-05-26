from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.auth import schemas
from app.auth.security import create_access_token, hash_password, verify_password


async def register(pool: asyncpg.Pool, req: schemas.RegisterRequest) -> schemas.AuthResponse:
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", req.email)
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

        async with conn.transaction():
            org = await conn.fetchrow(
                """
                INSERT INTO organisations (name, email)
                VALUES ($1, $2)
                RETURNING id, name, email, plan, max_chargers
                """,
                req.org_name, req.email,
            )
            user = await conn.fetchrow(
                """
                INSERT INTO users (org_id, email, password_hash, full_name, role)
                VALUES ($1, $2, $3, $4, 'owner')
                RETURNING id, email, full_name, role, created_at
                """,
                org["id"], req.email, hash_password(req.password), req.full_name,
            )

    return _build_auth_response(user, org)


async def login(pool: asyncpg.Pool, req: schemas.LoginRequest) -> schemas.AuthResponse:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.full_name, u.role, u.created_at, u.password_hash,
                   u.is_active, o.id AS org_id, o.name AS org_name, o.email AS org_email,
                   o.plan, o.max_chargers
            FROM users u JOIN organisations o ON o.id = u.org_id
            WHERE u.email = $1
            """,
            req.email,
        )
        if not row or not row["is_active"] or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
        await conn.execute(
            "UPDATE users SET last_login_at = $1 WHERE id = $2",
            datetime.now(timezone.utc), row["id"],
        )

    user = {
        "id": row["id"], "email": row["email"], "full_name": row["full_name"],
        "role": row["role"], "created_at": row["created_at"],
    }
    org = {
        "id": row["org_id"], "name": row["org_name"], "email": row["org_email"],
        "plan": row["plan"], "max_chargers": row["max_chargers"],
    }
    return _build_auth_response(user, org)


async def get_me(pool: asyncpg.Pool, user_id: UUID) -> schemas.MeResponse:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.full_name, u.role, u.created_at,
                   o.id AS org_id, o.name AS org_name, o.email AS org_email,
                   o.plan, o.max_chargers
            FROM users u JOIN organisations o ON o.id = u.org_id
            WHERE u.id = $1
            """,
            user_id,
        )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return schemas.MeResponse(
        user=schemas.UserOut(
            id=row["id"], email=row["email"], full_name=row["full_name"],
            role=row["role"], created_at=row["created_at"],
        ),
        organisation=schemas.OrgOut(
            id=row["org_id"], name=row["org_name"], email=row["org_email"],
            plan=row["plan"], max_chargers=row["max_chargers"],
        ),
    )


def _build_auth_response(user, org) -> schemas.AuthResponse:
    token = create_access_token(
        user_id=user["id"], org_id=org["id"], role=user["role"]
    )
    return schemas.AuthResponse(
        access_token=token,
        user=schemas.UserOut(
            id=user["id"], email=user["email"], full_name=user["full_name"],
            role=user["role"], created_at=user["created_at"],
        ),
        organisation=schemas.OrgOut(
            id=org["id"], name=org["name"], email=org["email"],
            plan=org["plan"], max_chargers=org["max_chargers"],
        ),
    )
