"""Superadmin administration logic."""
from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.auth.security import create_access_token
from . import schemas


async def create_org(pool: asyncpg.Pool, req: schemas.CreateOrgRequest) -> dict:
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM organisations WHERE email = $1", req.email)
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "organisation email already exists")

        row = await conn.fetchrow(
            """
            INSERT INTO organisations (name, email, plan)
            VALUES ($1, $2, $3)
            RETURNING id, name, email, plan, max_chargers, is_active, created_at
            """,
            req.name,
            req.email,
            req.plan,
        )
    return dict(row)


async def list_orgs(pool: asyncpg.Pool) -> list[schemas.OrgAdminOut]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.id, o.name, o.email, o.plan, o.max_chargers, o.is_active, o.created_at,
                   COUNT(c.cp_id)::int AS charger_count
            FROM organisations o
            LEFT JOIN chargers c ON c.org_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC
            """
        )
    return [schemas.OrgAdminOut(**dict(r)) for r in rows]


async def get_org_detail(pool: asyncpg.Pool, org_id: UUID) -> schemas.OrgDetailAdminOut:
    async with pool.acquire() as conn:
        org_row = await conn.fetchrow(
            """
            SELECT o.id, o.name, o.email, o.plan, o.max_chargers, o.is_active, o.created_at,
                   COUNT(c.cp_id)::int AS charger_count
            FROM organisations o
            LEFT JOIN chargers c ON c.org_id = o.id
            WHERE o.id = $1
            GROUP BY o.id
            """,
            org_id,
        )
        if not org_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "organisation not found")

        incidents_row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS cnt FROM incidents WHERE org_id = $1 AND resolved_at IS NULL",
            org_id,
        )
        sessions_row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS cnt FROM charger_sessions WHERE org_id = $1", org_id
        )

    return schemas.OrgDetailAdminOut(
        id=org_row["id"],
        name=org_row["name"],
        email=org_row["email"],
        plan=org_row["plan"],
        max_chargers=org_row["max_chargers"],
        is_active=org_row["is_active"],
        created_at=org_row["created_at"],
        charger_count=org_row["charger_count"],
        open_incidents_count=incidents_row["cnt"] if incidents_row else 0,
        total_sessions_count=sessions_row["cnt"] if sessions_row else 0,
    )


async def deactivate_org(pool: asyncpg.Pool, org_id: UUID) -> None:
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE organisations SET is_active = FALSE WHERE id = $1", org_id
        )
        if res == "UPDATE 0":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "organisation not found")


async def impersonate(pool: asyncpg.Pool, superadmin_id: UUID, org_id: UUID) -> str:
    async with pool.acquire() as conn:
        org = await conn.fetchrow("SELECT id, name FROM organisations WHERE id = $1", org_id)
        if not org:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "target organisation not found")

    # Generate JWT scoped to that org
    token = create_access_token(
        user_id=superadmin_id,
        org_id=org_id,
        role="owner",
        is_superadmin=True,
        impersonating=True,
    )
    return token


async def get_dashboard_stats(pool: asyncpg.Pool) -> schemas.AdminDashboardStats:
    async with pool.acquire() as conn:
        orgs_count = await conn.fetchrow("SELECT COUNT(*)::int AS cnt FROM organisations")
        chargers_count = await conn.fetchrow("SELECT COUNT(*)::int AS cnt FROM chargers")
        incidents_count = await conn.fetchrow(
            "SELECT COUNT(*)::int AS cnt FROM incidents WHERE resolved_at IS NULL"
        )
        
        # Calculate MRR dynamically: starter = ₹2,500, pro = ₹10,000, enterprise = ₹25,000
        mrr_row = await conn.fetchrow(
            """
            SELECT SUM(
                CASE plan
                    WHEN 'starter' THEN 2500
                    WHEN 'pro' THEN 10000
                    WHEN 'enterprise' THEN 25000
                    ELSE 0
                END
            )::double precision AS sum
            FROM organisations
            WHERE is_active = TRUE
            """
        )

    return schemas.AdminDashboardStats(
        total_orgs=orgs_count["cnt"] if orgs_count else 0,
        total_chargers=chargers_count["cnt"] if chargers_count else 0,
        total_incidents=incidents_count["cnt"] if incidents_count else 0,
        mrr=mrr_row["sum"] if mrr_row and mrr_row["sum"] is not None else 0.0,
    )
