"""FastAPI user management service logic."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import structlog
from fastapi import HTTPException, status

from . import schemas

log = structlog.get_logger()


async def list_users(pool: asyncpg.Pool, org_id: UUID) -> list[schemas.UserOut]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, org_id, email, full_name, role, is_active, created_at,
                   last_login_at, invited_by, invite_accepted_at
            FROM users
            WHERE org_id = $1
            ORDER BY created_at DESC
            """,
            org_id,
        )
    return [schemas.UserOut(**dict(r)) for r in rows]


async def invite_user(
    pool: asyncpg.Pool, org_id: UUID, invited_by_id: UUID, email: str, role: str
) -> schemas.UserOut:
    token = secrets.token_urlsafe(32)

    async with pool.acquire() as conn:
        # Check existing standard users
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

        # Check existing superadmins
        sa_existing = await conn.fetchrow("SELECT id FROM superadmins WHERE email = $1", email)
        if sa_existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

        async with conn.transaction():
            # Create pending user record
            row = await conn.fetchrow(
                """
                INSERT INTO users (org_id, email, password_hash, full_name, role, is_active, invited_by, invite_token)
                VALUES ($1, $2, '', 'Pending', $3, FALSE, $4, $5)
                RETURNING id, org_id, email, full_name, role, is_active, created_at, invited_by
                """,
                org_id,
                email,
                role,
                invited_by_id,
                token,
            )
            # Retrieve org and inviter names for the email
            org = await conn.fetchrow("SELECT name FROM organisations WHERE id = $1", org_id)
            inviter = await conn.fetchrow("SELECT full_name FROM users WHERE id = $1", invited_by_id)

    org_name = org["name"] if org else "ChargePulse Organisation"
    inviter_name = inviter["full_name"] if inviter else "An Administrator"

    # Format email body precisely as requested
    email_body = f"""Subject: You're invited to ChargePulse — {org_name}

Hi,

{inviter_name} has invited you to join {org_name} on ChargePulse as {role}.

Click below to set up your account:
https://app.chargepulse.in/accept-invite?token={token}

This link expires in 7 days.

— ChargePulse"""

    log.info("Invite email logged", email=email, token=token, email_body=email_body)

    # Print to console so it is easily visible to developer
    print("\n" + "=" * 60)
    print(email_body)
    print("=" * 60 + "\n")

    return schemas.UserOut(**dict(row))


async def remove_user(pool: asyncpg.Pool, org_id: UUID, user_id: UUID) -> None:
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM users WHERE id = $1 AND org_id = $2", user_id, org_id
        )
        # Check rows deleted
        if res == "DELETE 0":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")


async def update_user_role(
    pool: asyncpg.Pool, org_id: UUID, user_id: UUID, role: str
) -> schemas.UserOut:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET role = $1
            WHERE id = $2 AND org_id = $3
            RETURNING id, org_id, email, full_name, role, is_active, created_at,
                      last_login_at, invited_by, invite_accepted_at
            """,
            role,
            user_id,
            org_id,
        )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return schemas.UserOut(**dict(row))
