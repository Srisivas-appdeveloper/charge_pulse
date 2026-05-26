"""End-to-end onboarding: register a CPO, bulk-import chargers, set up alerts.

Usage:
    .venv/bin/python scripts/seed_demo_data.py \\
        --org "ChargeZone Chennai" --email cto@chargezone.in --password supersecret \\
        --csv data/chargers.csv

The CSV must have columns:
    cp_id,display_name,vendor,model,city,state,pincode,lat,lng

After completion, prints the OCPP WebSocket URLs to share with the CPO so they
can point their chargers at the gateway.
"""
import argparse
import csv
import sys
from pathlib import Path

import httpx

DEFAULT_API = "http://localhost:8000/api/v1"
GATEWAY_BASE = "ws://localhost:9000/ocpp"  # adjust for prod (wss://csms.chargepulse.in/ocpp)


def parse_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "cp_id": r["cp_id"].strip(),
                "display_name": r.get("display_name") or None,
                "vendor": r.get("vendor") or None,
                "model": r.get("model") or None,
                "city": r.get("city") or None,
                "state": r.get("state") or None,
                "pincode": r.get("pincode") or None,
                "lat": float(r["lat"]) if r.get("lat") else None,
                "lng": float(r["lng"]) if r.get("lng") else None,
                "connector_count": int(r.get("connector_count", "1") or 1),
            })
    return rows


def register(api: str, org: str, email: str, password: str, full_name: str) -> str:
    """Try register; if conflict, fall back to login. Returns token."""
    r = httpx.post(f"{api}/auth/register", json={
        "org_name": org, "email": email, "password": password, "full_name": full_name,
    })
    if r.status_code == 200:
        print(f"Registered new org: {org}")
        return r.json()["access_token"]
    if r.status_code == 409:
        print("Email exists — logging in instead.")
        r = httpx.post(f"{api}/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]
    r.raise_for_status()


def bulk_import(api: str, token: str, chargers: list[dict]) -> dict:
    r = httpx.post(
        f"{api}/chargers/bulk",
        headers={"Authorization": f"Bearer {token}"},
        json={"chargers": chargers}, timeout=60,
    )
    r.raise_for_status()
    return r.json()


def setup_alerts(api: str, token: str, email: str, webhook: str | None) -> None:
    configs = [{"channel": "email", "endpoint": email, "label": "Owner email", "severity_min": "high"}]
    if webhook:
        configs.append({"channel": "webhook", "endpoint": webhook, "label": "Ops webhook", "severity_min": "medium"})
    for c in configs:
        r = httpx.post(
            f"{api}/alerts/config",
            headers={"Authorization": f"Bearer {token}"},
            json=c,
        )
        if r.status_code >= 400:
            print(f"  alert config failed ({c['channel']}): {r.text}")
        else:
            print(f"  alert channel ready: {c['channel']} → {c['endpoint']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--gateway", default=GATEWAY_BASE)
    ap.add_argument("--org", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--full-name", default="Admin")
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--webhook", default=None)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr); sys.exit(1)

    rows = parse_csv(args.csv)
    print(f"Parsed {len(rows)} charger rows.")

    token = register(args.api, args.org, args.email, args.password, args.full_name)
    result = bulk_import(args.api, token, rows)
    print(f"Created {result['created']} chargers, skipped {len(result['skipped'])}.")
    for s in result["skipped"]:
        print(f"  - {s['cp_id']}: {s['reason']}")

    print("Setting up default alert channels...")
    setup_alerts(args.api, token, args.email, args.webhook)

    print()
    print("=" * 60)
    print("Onboarding complete. Point each charger's CSMS URL at:")
    print("=" * 60)
    for row in rows:
        print(f"  {args.gateway}/{row['cp_id']}")


if __name__ == "__main__":
    main()
