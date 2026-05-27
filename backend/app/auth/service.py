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
                INSERT INTO users (org_id, email, password_hash, full_name, role, phone_number)
                VALUES ($1, $2, $3, $4, 'owner', $5)
                RETURNING id, email, full_name, role, created_at
                """,
                org["id"], req.email, hash_password(req.password), req.full_name, req.phone_number,
            )

    return _build_auth_response(user, org)


async def login(pool: asyncpg.Pool, req: schemas.LoginRequest) -> schemas.AuthResponse:
    async with pool.acquire() as conn:
        # Check superadmins table first
        sa_row = await conn.fetchrow(
            "SELECT id, email, password_hash, full_name, created_at FROM superadmins WHERE email = $1",
            req.email,
        )
        if sa_row:
            if not verify_password(req.password, sa_row["password_hash"]):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
            
            user = {
                "id": sa_row["id"],
                "email": sa_row["email"],
                "full_name": sa_row["full_name"],
                "role": "superadmin",
                "created_at": sa_row["created_at"],
            }
            return _build_auth_response(user, None, is_superadmin=True)

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
        
        # Enforce that only 'owner' role can login for now
        if row["role"] != "owner":
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
        # Check superadmins first
        sa_row = await conn.fetchrow(
            "SELECT id, email, full_name, created_at FROM superadmins WHERE id = $1",
            user_id,
        )
        if sa_row:
            return schemas.MeResponse(
                user=schemas.UserOut(
                    id=sa_row["id"], email=sa_row["email"], full_name=sa_row["full_name"],
                    role="superadmin", created_at=sa_row["created_at"],
                ),
                organisation=None,
            )

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


async def accept_invite(pool: asyncpg.Pool, req: schemas.AcceptInviteRequest) -> schemas.AuthResponse:
    async with pool.acquire() as conn:
        # Find user by invite_token
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.role, u.created_at,
                   o.id AS org_id, o.name AS org_name, o.email AS org_email,
                   o.plan, o.max_chargers
            FROM users u JOIN organisations o ON o.id = u.org_id
            WHERE u.invite_token = $1
            """,
            req.token,
        )
        if not row:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired invite token")

        # Update user details
        hashed_pwd = hash_password(req.password)
        await conn.execute(
            """
            UPDATE users
            SET full_name = $1, password_hash = $2, invite_token = NULL,
                invite_accepted_at = $3, is_active = TRUE
            WHERE id = $4
            """,
            req.full_name, hashed_pwd, datetime.now(timezone.utc), row["id"],
        )

    user = {
        "id": row["id"], "email": row["email"], "full_name": req.full_name,
        "role": row["role"], "created_at": row["created_at"],
    }
    org = {
        "id": row["org_id"], "name": row["org_name"], "email": row["org_email"],
        "plan": row["plan"], "max_chargers": row["max_chargers"],
    }
    return _build_auth_response(user, org)


async def update_profile(pool: asyncpg.Pool, user_id: UUID, req: schemas.UpdateProfileRequest) -> schemas.UserOut:
    async with pool.acquire() as conn:
        # Check superadmins
        sa_row = await conn.fetchrow(
            "SELECT id, email, full_name, created_at FROM superadmins WHERE id = $1",
            user_id,
        )
        if sa_row:
            if req.full_name:
                await conn.execute("UPDATE superadmins SET full_name = $1 WHERE id = $2", req.full_name, user_id)
            if req.password:
                await conn.execute("UPDATE superadmins SET password_hash = $1 WHERE id = $2", hash_password(req.password), user_id)
            
            updated = await conn.fetchrow(
                "SELECT id, email, full_name, created_at FROM superadmins WHERE id = $1",
                user_id,
            )
            return schemas.UserOut(
                id=updated["id"], email=updated["email"], full_name=updated["full_name"],
                role="superadmin", created_at=updated["created_at"],
            )

        # Update standard users
        user_row = await conn.fetchrow("SELECT id, email, role, created_at FROM users WHERE id = $1", user_id)
        if not user_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

        if req.full_name:
            await conn.execute("UPDATE users SET full_name = $1 WHERE id = $2", req.full_name, user_id)
        if req.password:
            await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", hash_password(req.password), user_id)

        updated = await conn.fetchrow("SELECT id, email, full_name, role, created_at FROM users WHERE id = $1", user_id)
        return schemas.UserOut(
            id=updated["id"], email=updated["email"], full_name=updated["full_name"],
            role=updated["role"], created_at=updated["created_at"],
        )


def _build_auth_response(user, org, is_superadmin=False, impersonating=False) -> schemas.AuthResponse:
    token = create_access_token(
        user_id=user["id"], org_id=org["id"] if org else None, role=user["role"],
        is_superadmin=is_superadmin, impersonating=impersonating,
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
        ) if org else None,
    )
