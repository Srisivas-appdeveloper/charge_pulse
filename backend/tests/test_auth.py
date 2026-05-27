"""Integration tests for RBAC, user management, and superadmin impersonation."""
from __future__ import annotations

import os
import secrets
import socket
from pathlib import Path

import asyncpg
import httpx
import pytest
from dotenv import load_dotenv

BASE = "http://localhost:8000/api/v1"


def _api_up() -> bool:
    try:
        with socket.create_connection(("localhost", 8000), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _api_up(), reason="API not running on :8000")

# Load environment variables
env_path = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)


async def get_db_conn():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    db = os.getenv("POSTGRES_DB", "chargepulse")
    user = os.getenv("POSTGRES_USER", "chargepulse")
    pw = os.getenv("POSTGRES_PASSWORD", "change_me_in_production")
    return await asyncpg.connect(host=host, port=port, database=db, user=user, password=pw)


def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.asyncio
async def test_registration_creates_owner_role():
    """Verify that registering an organization creates an owner user."""
    suffix = secrets.token_hex(4)
    email = f"owner+{suffix}@chargepulse.example.com"
    body = {
        "org_name": f"Owner Org {suffix}",
        "email": email,
        "password": "supersecret123",
        "full_name": "Owner User",
        "phone_number": "9876543210",
    }
    r = httpx.post(f"{BASE}/auth/register", json=body)
    assert r.status_code == 200, r.text
    res_data = r.json()
    assert res_data["user"]["role"] == "owner"
    assert res_data["user"]["email"] == email


@pytest.mark.asyncio
async def test_pending_invitations_and_flow():
    """Test the complete invitation and accept invitation flow."""
    suffix = secrets.token_hex(4)
    owner_email = f"owner+{suffix}@chargepulse.example.com"
    member_email = f"member+{suffix}@chargepulse.example.com"

    # Register owner
    r = httpx.post(
        f"{BASE}/auth/register",
        json={
            "org_name": f"Invite Org {suffix}",
            "email": owner_email,
            "password": "supersecret123",
            "full_name": "Inviter Owner",
            "phone_number": "9876543210",
        },
    )
    assert r.status_code == 200
    owner_token = r.json()["access_token"]

    # Owner invites a member
    r = httpx.post(
        f"{BASE}/users/invite",
        headers=_h(owner_token),
        json={"email": member_email, "role": "member"},
    )
    assert r.status_code == 200, r.text
    invited_user_id = r.json()["id"]

    # Verify user is in db and is not active yet
    conn = await get_db_conn()
    try:
        row = await conn.fetchrow("SELECT invite_token, is_active FROM users WHERE id = $1", invited_user_id)
        assert row is not None
        assert row["is_active"] is False
        invite_token = row["invite_token"]
        assert invite_token is not None

        # Trying to login as pending user fails
        login_res = httpx.post(
            f"{BASE}/auth/login",
            json={"email": member_email, "password": "newpassword123"},
        )
        assert login_res.status_code == 401

        # Accept the invitation
        accept_res = httpx.post(
            f"{BASE}/auth/accept-invite",
            json={
                "token": invite_token,
                "full_name": "Accepted Member",
                "password": "newpassword123",
            },
        )
        assert accept_res.status_code == 200, accept_res.text
        member_token = accept_res.json()["access_token"]

        # Verify member cannot log in via /login because only 'owner' role works for now
        login_res = httpx.post(
            f"{BASE}/auth/login",
            json={"email": member_email, "password": "newpassword123"},
        )
        assert login_res.status_code == 401

        # Member attempts to delete a charger (should fail with 403)
        del_res = httpx.delete(f"{BASE}/chargers/non-existent-charger", headers=_h(member_token))
        assert del_res.status_code == 403
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_superadmin_and_impersonation():
    """Verify superadmin login, client org listing, and impersonation flow."""
    # Use seeded platform superadmin: saravanan@chargepulse.in / chargepulse123
    r = httpx.post(
        f"{BASE}/auth/login",
        json={"email": "saravanan@chargepulse.in", "password": "chargepulse123"},
    )
    assert r.status_code == 200, r.text
    sa_token = r.json()["access_token"]
    assert r.json()["user"]["role"] == "superadmin"

    # Get client list from admin panel
    r = httpx.get(f"{BASE}/admin/orgs", headers=_h(sa_token))
    assert r.status_code == 200
    orgs = r.json()
    assert len(orgs) > 0

    target_org = orgs[0]
    target_org_id = target_org["id"]

    # Impersonate that organization
    r = httpx.post(f"{BASE}/admin/impersonate/{target_org_id}", headers=_h(sa_token))
    assert r.status_code == 200
    impersonate_token = r.json()["access_token"]

    # Verify access to chargers of that org (should succeed without 403)
    r = httpx.get(f"{BASE}/chargers", headers=_h(impersonate_token))
    assert r.status_code == 200
