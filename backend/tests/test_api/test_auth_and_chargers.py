"""Integration tests against the live local API (port 8000).

These are smoke tests, not isolated unit tests — they require the API + DB +
Redis to be running. Skip cleanly when the API is unreachable so CI without
the stack doesn't fail noisily.
"""
import secrets
import socket

import httpx
import pytest

BASE = "http://localhost:8000/api/v1"


def _api_up() -> bool:
    try:
        with socket.create_connection(("localhost", 8000), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _api_up(), reason="API not running on :8000")


@pytest.fixture(scope="module")
def session_token():
    """Register a throwaway org each run so tests are self-contained."""
    suffix = secrets.token_hex(4)
    email = f"test+{suffix}@chargepulse.example.com"
    body = {
        "org_name": f"Test Org {suffix}", "email": email,
        "password": "supersecret123", "full_name": "Pytest Runner",
        "phone_number": "1234567890",
    }
    r = httpx.post(f"{BASE}/auth/register", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t): return {"Authorization": f"Bearer {t}"}


def test_unauthenticated_request_is_rejected():
    r = httpx.get(f"{BASE}/chargers")
    assert r.status_code == 401


def test_me_returns_user_and_org(session_token):
    r = httpx.get(f"{BASE}/auth/me", headers=_h(session_token))
    assert r.status_code == 200
    body = r.json()
    assert "user" in body and "organisation" in body
    assert body["organisation"]["plan"] == "starter"


def test_charger_crud_and_multitenancy_isolation(session_token):
    cp_id = f"CP-TEST-{secrets.token_hex(3)}"
    # create
    r = httpx.post(f"{BASE}/chargers", headers=_h(session_token), json={
        "cp_id": cp_id, "display_name": "pytest charger",
        "vendor": "Delta", "city": "Chennai", "lat": 13.0, "lng": 80.2,
    })
    assert r.status_code == 201, r.text
    # list contains it
    r = httpx.get(f"{BASE}/chargers", headers=_h(session_token))
    cp_ids = [c["cp_id"] for c in r.json()["chargers"]]
    assert cp_id in cp_ids
    # second org cannot see it
    other_email = f"other+{secrets.token_hex(4)}@chargepulse.example.com"
    r2 = httpx.post(f"{BASE}/auth/register", json={
        "org_name": "Other", "email": other_email,
        "password": "supersecret123", "full_name": "Other",
        "phone_number": "1234567890",
    })
    assert r2.status_code == 200
    other_token = r2.json()["access_token"]
    r3 = httpx.get(f"{BASE}/chargers", headers=_h(other_token))
    assert cp_id not in [c["cp_id"] for c in r3.json()["chargers"]]


def test_fleet_overview_shape(session_token):
    r = httpx.get(f"{BASE}/fleet/overview", headers=_h(session_token))
    assert r.status_code == 200
    body = r.json()
    for k in ["total_chargers", "online", "offline", "faulted",
              "avg_health_score", "open_incidents", "sessions_today"]:
        assert k in body, f"missing {k}"


def test_alert_config_crud(session_token):
    # create
    r = httpx.post(f"{BASE}/alerts/config", headers=_h(session_token), json={
        "channel": "webhook", "endpoint": "https://example.com/hook",
        "label": "pytest", "severity_min": "low",
    })
    assert r.status_code == 201
    cid = r.json()["id"]
    # list contains
    r2 = httpx.get(f"{BASE}/alerts/config", headers=_h(session_token))
    assert any(c["id"] == cid for c in r2.json()["configs"])
    # delete
    r3 = httpx.delete(f"{BASE}/alerts/config/{cid}", headers=_h(session_token))
    assert r3.status_code == 204
