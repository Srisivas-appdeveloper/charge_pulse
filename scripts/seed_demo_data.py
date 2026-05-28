"""End-to-end demo seeder for ChargePulse.

Two modes:

  python3 scripts/seed_demo_data.py --full
      One-command demo build:
        - org "Demo CPO" with an owner login
        - 20 chargers across Chennai + Coimbatore with real GPS
        - 14 days of synthetic feature_vectors per charger
        - LSTM anomaly models trained for 5 chargers
        - 3 chargers with injected faults + degraded health
        - 8 incidents (mix of severities, some resolved)

  python3 scripts/seed_demo_data.py --org "Foo" --email a@b.in --password X --csv FILE
      Original CPO onboarding flow: register + bulk-import chargers from CSV.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import httpx

# Allow importing from backend/ for the LSTM trainer
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import asyncpg  # noqa: E402
import bcrypt  # noqa: E402
import numpy as np  # noqa: E402

DEFAULT_API = "http://localhost:8000/api/v1"
GATEWAY_BASE = "ws://localhost:9000/ocpp"


# ---------------------------------------------------------------------------
# Original CSV onboarding mode (preserved)
# ---------------------------------------------------------------------------
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


def run_csv_mode(args) -> None:
    if not Path(args.csv).exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr); sys.exit(1)
    rows = parse_csv(Path(args.csv))
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


# ---------------------------------------------------------------------------
# --full demo mode
# ---------------------------------------------------------------------------

# 20 chargers across Chennai + Coimbatore with real GPS
DEMO_CHARGERS = [
    # Chennai
    ("CP-CHN-001", "T Nagar Pondy Bazaar Hub",   "Delta",     "DC-50",     "Chennai",    "TN", "600017", 13.0418, 80.2341),
    ("CP-CHN-002", "Anna Nagar Tower 2",         "Delta",     "DC-60",     "Chennai",    "TN", "600040", 13.0850, 80.2101),
    ("CP-CHN-003", "Phoenix Marketcity",         "ABB",       "Terra-54",  "Chennai",    "TN", "600107", 12.9923, 80.2178),
    ("CP-CHN-004", "Express Avenue Mall",        "ABB",       "Terra-54",  "Chennai",    "TN", "600002", 13.0608, 80.2641),
    ("CP-CHN-005", "VR Mall Anna Nagar",         "Exicom",    "Harmony-25","Chennai",    "TN", "600040", 13.0827, 80.2114),
    ("CP-CHN-006", "OMR Sholinganallur Hub",     "Servotech", "RAPID-60",  "Chennai",    "TN", "600119", 12.8995, 80.2272),
    ("CP-CHN-007", "DLF Cybercity",              "Delta",     "DC-50",     "Chennai",    "TN", "603103", 12.8412, 80.1568),
    ("CP-CHN-008", "Tidel Park Taramani",        "ABB",       "Terra-54",  "Chennai",    "TN", "600113", 12.9851, 80.2477),
    ("CP-CHN-009", "Chennai Citi Centre",        "Exicom",    "Harmony-25","Chennai",    "TN", "600028", 13.0249, 80.2696),
    ("CP-CHN-010", "Forum Vijaya Mall",          "Servotech", "RAPID-60",  "Chennai",    "TN", "600026", 13.0407, 80.2147),
    ("CP-CHN-011", "Spencer Plaza",              "Delta",     "DC-50",     "Chennai",    "TN", "600002", 13.0598, 80.2616),
    ("CP-CHN-012", "Marina Beach Parking",       "ABB",       "Terra-54",  "Chennai",    "TN", "600005", 13.0500, 80.2824),
    # Coimbatore
    ("CP-CBE-001", "Brookefields Mall",          "Delta",     "DC-50",     "Coimbatore", "TN", "641009", 11.0168, 76.9558),
    ("CP-CBE-002", "Fun Republic Mall",          "ABB",       "Terra-54",  "Coimbatore", "TN", "641012", 11.0241, 76.9716),
    ("CP-CBE-003", "Prozone Mall",               "Exicom",    "Harmony-25","Coimbatore", "TN", "641013", 11.0438, 77.0017),
    ("CP-CBE-004", "Codissia Trade Fair",        "Servotech", "RAPID-60",  "Coimbatore", "TN", "641014", 11.0299, 77.0432),
    ("CP-CBE-005", "Race Course Junction",       "Delta",     "DC-60",     "Coimbatore", "TN", "641018", 11.0011, 76.9750),
    ("CP-CBE-006", "Gandhipuram Bus Stand",      "ABB",       "Terra-54",  "Coimbatore", "TN", "641012", 11.0182, 76.9628),
    ("CP-CBE-007", "PSG Tech Campus",            "Exicom",    "Harmony-25","Coimbatore", "TN", "641004", 11.0245, 77.0040),
    ("CP-CBE-008", "Saibaba Colony Hub",         "Servotech", "RAPID-60",  "Coimbatore", "TN", "641011", 11.0218, 76.9457),
]
assert len(DEMO_CHARGERS) == 20

TRAINED_IDS = ["CP-CHN-001", "CP-CHN-002", "CP-CHN-003", "CP-CBE-001", "CP-CBE-002"]
FAULTED_PLAN = [
    # (cp_id, fault_mode, mapped_failure_type, severity)
    ("CP-CHN-006", "voltage_low",       "power_supply",       "high"),
    ("CP-CBE-004", "heartbeat_missing", "communication_loss", "critical"),
    ("CP-CHN-010", "session_failures",  "connector_fault",    "medium"),
]


def _pg_settings() -> dict:
    """Read PG creds from backend/.env (no pydantic import to keep this script light)."""
    env_path = ROOT / "backend" / ".env"
    creds = {"host": "localhost", "port": 5433, "db": "chargepulse",
             "user": "chargepulse", "password": "change_me_in_production"}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == "POSTGRES_HOST":       creds["host"] = v
            elif k == "POSTGRES_PORT":     creds["port"] = int(v)
            elif k == "POSTGRES_DB":       creds["db"] = v
            elif k == "POSTGRES_USER":     creds["user"] = v
            elif k == "POSTGRES_PASSWORD": creds["password"] = v
    return creds


async def _connect() -> asyncpg.Pool:
    c = _pg_settings()
    return await asyncpg.create_pool(
        host=c["host"], port=c["port"], database=c["db"],
        user=c["user"], password=c["password"],
    )


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


async def ensure_org_and_owner(pool, *, org_name: str, owner_email: str,
                               owner_name: str, owner_password: str) -> tuple[UUID, UUID]:
    async with pool.acquire() as conn:
        org_id = await conn.fetchval(
            "SELECT id FROM organisations WHERE name = $1", org_name,
        )
        if not org_id:
            org_id = await conn.fetchval(
                "INSERT INTO organisations (name, email, plan, max_chargers) "
                "VALUES ($1, $2, 'pro', 100) RETURNING id",
                org_name, f"billing@{org_name.lower().replace(' ', '')}.in",
            )
            print(f"  created org '{org_name}'")
        else:
            print(f"  org '{org_name}' already exists")

        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", owner_email,
        )
        if not user_id:
            user_id = await conn.fetchval(
                "INSERT INTO users (org_id, email, password_hash, full_name, role) "
                "VALUES ($1, $2, $3, $4, 'owner') RETURNING id",
                org_id, owner_email, _hash(owner_password), owner_name,
            )
            print(f"  created owner {owner_email} (password: {owner_password})")
        else:
            await conn.execute(
                "UPDATE users SET password_hash = $1, org_id = $2 WHERE id = $3",
                _hash(owner_password), org_id, user_id,
            )
            print(f"  owner {owner_email} exists — password reset to '{owner_password}'")
    return org_id, user_id


async def upsert_chargers(pool, org_id: UUID) -> int:
    async with pool.acquire() as conn:
        for (cp_id, name, vendor, model, city, state, pincode, lat, lng) in DEMO_CHARGERS:
            await conn.execute(
                """
                INSERT INTO chargers (
                  cp_id, org_id, display_name, vendor, model, connector_count,
                  location, city, state, pincode, status, health_score,
                  commissioned_at
                ) VALUES (
                  $1, $2, $3, $4, $5, 2,
                  ST_SetSRID(ST_MakePoint($6, $7), 4326)::geography,
                  $8, $9, $10, 'online', 96.0,
                  NOW() - INTERVAL '120 days'
                )
                ON CONFLICT (cp_id) DO UPDATE SET
                  org_id = EXCLUDED.org_id,
                  display_name = EXCLUDED.display_name,
                  vendor = EXCLUDED.vendor,
                  model = EXCLUDED.model,
                  location = EXCLUDED.location,
                  city = EXCLUDED.city,
                  state = EXCLUDED.state,
                  pincode = EXCLUDED.pincode,
                  status = 'online',
                  health_score = 96.0
                """,
                cp_id, org_id, name, vendor, model, lng, lat, city, state, pincode,
            )
    return len(DEMO_CHARGERS)


def _synth_window(t: datetime, rng: np.random.Generator,
                  *, fault: str | None = None) -> list[float]:
    """Healthy 15-min feature vector, with optional fault injection."""
    hour = t.hour + t.minute / 60
    daily_factor = math.exp(-((hour - 16) ** 2) / 30)
    sessions_started = max(0, int(rng.normal(daily_factor * 2.0, 1.0)))
    completed = max(0, sessions_started - int(rng.integers(0, 2)))
    failed = max(0, sessions_started - completed)

    if fault == "session_failures":
        failed = sessions_started
        completed = 0

    avg_dur = float(rng.normal(35, 10)) if sessions_started else 0.0
    avg_energy = float(rng.normal(18, 4)) if sessions_started else 0.0
    completion = (completed / sessions_started) if sessions_started else 1.0

    avg_power = float(rng.normal(22, 3)) if sessions_started else 0.0
    std_power = float(abs(rng.normal(1.5, 0.5))) if sessions_started else 0.0

    voltage_mean = 190.0 if fault == "voltage_low" else float(rng.normal(230, 3))
    max_v = voltage_mean + abs(rng.normal(5, 2))
    min_v = voltage_mean - abs(rng.normal(5, 2))
    avg_i = float(rng.normal(20, 4)) if sessions_started else 0.0
    pf = float(np.clip(rng.normal(0.95, 0.02), 0.7, 1.0))

    status_trans = sessions_started * 2 + int(rng.integers(0, 2))
    faulted_pct = 0.3 if fault else 0.0
    available_pct = float(np.clip(rng.normal(0.65 if fault else 0.95, 0.03), 0, 1))
    unavailable_pct = max(0.0, 1 - available_pct - faulted_pct)
    error_count = int(rng.integers(2, 6)) if fault else 0
    unique_errors = min(error_count, 3) if fault else 0

    if fault == "heartbeat_missing":
        hb_count = int(rng.normal(20, 5))
        hb_gap_max = float(rng.normal(180, 30))
        hb_gap_std = float(rng.normal(45, 10))
        ws_reconnects = int(rng.integers(3, 8))
    else:
        hb_count = int(rng.normal(150, 5))
        hb_gap_max = float(rng.normal(6.5, 0.5))
        hb_gap_std = float(abs(rng.normal(0.1, 0.05)))
        ws_reconnects = 0

    hour_sin = math.sin(2 * math.pi * hour / 24.0)
    day_sin = math.sin(2 * math.pi * t.weekday() / 7.0)
    return [
        float(sessions_started), float(completed), float(failed),
        avg_dur, avg_energy, completion,
        avg_power, std_power, max_v, min_v, avg_i, pf,
        float(status_trans), faulted_pct, available_pct, unavailable_pct,
        float(error_count), float(unique_errors),
        float(hb_count), hb_gap_max, hb_gap_std, float(ws_reconnects),
        hour_sin, day_sin,
    ]


async def seed_features(pool, org_id: UUID, days: int,
                        faulted: dict[str, str]) -> int:
    """Insert days*96 feature vectors per charger. For chargers in `faulted`,
    inject the fault pattern in the most recent 6 hours."""
    rng = np.random.default_rng(42)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    now = now - timedelta(minutes=now.minute % 15)
    fault_cutoff = now - timedelta(hours=6)

    total = 0
    async with pool.acquire() as conn:
        for (cp_id, *_rest) in DEMO_CHARGERS:
            await conn.execute(
                "DELETE FROM feature_vectors WHERE cp_id = $1", cp_id,
            )
            fault = faulted.get(cp_id)
            rows = []
            for i in range(days * 96):
                t = now - timedelta(minutes=15 * i)
                active_fault = fault if (fault and t >= fault_cutoff) else None
                rows.append((t, cp_id, org_id, _synth_window(t, rng, fault=active_fault)))
            await conn.executemany(
                "INSERT INTO feature_vectors (time, cp_id, org_id, features) "
                "VALUES ($1, $2, $3, $4)",
                rows,
            )
            total += len(rows)
    return total


async def degrade_faulted_chargers(pool, plan: list[tuple]) -> None:
    async with pool.acquire() as conn:
        for (cp_id, _fault, _ftype, severity) in plan:
            health = {"critical": 35.0, "high": 55.0, "medium": 70.0}.get(severity, 60.0)
            status = "faulted" if severity in ("critical", "high") else "online"
            await conn.execute(
                "UPDATE chargers SET status = $1, health_score = $2, "
                "last_heartbeat_at = NOW() - INTERVAL '10 minutes' WHERE cp_id = $3",
                status, health, cp_id,
            )


async def seed_incidents(pool, org_id: UUID) -> int:
    now = datetime.now(timezone.utc)
    plan = [
        ("CP-CHN-006", "high",     "power_supply",
         "Voltage drop below 200 V sustained for 45 min",
         "Average voltage 192 V vs nominal 230 V. Likely upstream transformer issue.",
         3, None, 0.087),
        ("CP-CBE-004", "critical", "communication_loss",
         "Heartbeat lost — no contact for 8 minutes",
         "Charger stopped responding. Last heartbeat: 8 minutes ago.",
         1, None, 0.142),
        ("CP-CHN-010", "medium",   "connector_fault",
         "5 consecutive failed sessions",
         "All sessions ended with 'PowerLoss' before user-initiated stop.",
         5, None, 0.061),
        ("CP-CHN-003", "high",     "thermal_overload",
         "Connector temperature exceeded threshold",
         "Connector A reached 78°C during peak charging. Auto-derated to 32 kW.",
         12, 6, 0.094),
        ("CP-CBE-002", "low",      "firmware_crash",
         "Charger rebooted unexpectedly twice",
         "Firmware v2.4.1 known issue. Vendor patch v2.4.2 available.",
         28, 22, 0.038),
        ("CP-CHN-002", "medium",   "payment_system",
         "RFID reader intermittent failure",
         "30% of RFID swipes returning timeout. Backend authorization OK.",
         48, 30, 0.052),
        ("CP-CHN-001", "low",      "ground_fault",
         "Ground fault detection circuit triggered (cleared)",
         "Self-test caught a transient ground fault during boot. No service impact.",
         72, 71, 0.029),
        ("CP-CBE-001", "critical", "power_supply",
         "Phase imbalance — derated to single-phase",
         "Phase B voltage 0 V. Charger derated from 50 kW to 7 kW until fixed.",
         96, 80, 0.118),
    ]
    async with pool.acquire() as conn:
        # Idempotent: wipe synthesized incidents (those matching titles) for this org
        await conn.execute(
            "DELETE FROM incidents WHERE org_id = $1 AND title = ANY($2::text[])",
            org_id, [p[3] for p in plan],
        )
        for (cp_id, sev, ftype, title, desc, det_h, res_h, score) in plan:
            await conn.execute(
                """
                INSERT INTO incidents
                  (cp_id, org_id, severity, failure_type, title, description,
                   anomaly_score, auto_detected, detected_at,
                   acknowledged_at, resolved_at, confirmed_failure_type)
                VALUES ($1, $2, $3, $4, $5, $6, $7, true,
                        $8, $9, $10, $11)
                """,
                cp_id, org_id, sev, ftype, title, desc, score,
                now - timedelta(hours=det_h),
                (now - timedelta(hours=det_h - 0.25)) if res_h else None,
                (now - timedelta(hours=res_h)) if res_h else None,
                ftype if res_h else None,
            )
    return len(plan)


async def add_default_alert_configs(pool, org_id: UUID, owner_email: str) -> int:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM alert_configs WHERE org_id = $1", org_id)
        rows = [
            (org_id, "email",   owner_email,                                  "Owner email",        "medium"),
            (org_id, "slack",   "https://hooks.slack.com/services/T0/B0/XXX", "Ops Slack",          "high"),
            (org_id, "webhook", "https://ops.democpo.in/hooks/chargepulse",   "Internal PagerDuty", "critical"),
        ]
        for r in rows:
            await conn.execute(
                "INSERT INTO alert_configs (org_id, channel, endpoint, label, severity_min) "
                "VALUES ($1, $2, $3, $4, $5)", *r,
            )
    return len(rows)


async def train_anomaly_models(cp_ids: list[str]) -> dict[str, str]:
    """Train an LSTM autoencoder for each charger. Lazy-imported so non-`--full`
    runs (and `--skip-training`) don't pay the torch import cost."""
    from ml.training.train_anomaly import train as train_one  # noqa: WPS433

    results: dict[str, str] = {}
    for cp_id in cp_ids:
        print(f"  → training LSTM for {cp_id} ...")
        try:
            await train_one(cp_id, days=14, epochs=20)
            results[cp_id] = "ok"
        except Exception as exc:
            results[cp_id] = f"FAILED: {exc}"
            print(f"     {results[cp_id]}")
    return results


async def run_full(args) -> None:
    pool = await _connect()
    try:
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  ChargePulse Demo Seeder — building full demo dataset")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        print("▶ Step 1/6  ensure org + owner")
        org_id, _ = await ensure_org_and_owner(
            pool,
            org_name=args.demo_org,
            owner_email=args.demo_email,
            owner_name="Demo CPO Owner",
            owner_password=args.demo_password,
        )

        print(f"\n▶ Step 2/6  upsert {len(DEMO_CHARGERS)} chargers (Chennai + Coimbatore)")
        n = await upsert_chargers(pool, org_id)
        print(f"  {n} chargers ready")

        print(f"\n▶ Step 3/6  generate 14 days of feature vectors per charger")
        faulted_map = {cp: fault for (cp, fault, _, _) in FAULTED_PLAN}
        total_features = await seed_features(pool, org_id, days=14, faulted=faulted_map)
        print(f"  {total_features:,} feature vectors inserted "
              f"({len(faulted_map)} chargers have last-6h faults injected)")

        print(f"\n▶ Step 4/6  mark 3 chargers as faulted on the dashboard")
        await degrade_faulted_chargers(pool, FAULTED_PLAN)
        for (cp, fault, _, sev) in FAULTED_PLAN:
            print(f"  {cp}: {fault} ({sev})")

        print(f"\n▶ Step 5/6  seed 8 incidents (open + resolved) and alert channels")
        n_inc = await seed_incidents(pool, org_id)
        print(f"  {n_inc} incidents inserted")
        n_alerts = await add_default_alert_configs(pool, org_id, args.demo_email)
        print(f"  {n_alerts} alert channels configured")

        if args.skip_training:
            print("\n▶ Step 6/6  SKIPPED (--skip-training)")
        else:
            print(f"\n▶ Step 6/6  train LSTM anomaly models for {len(TRAINED_IDS)} chargers")
            print("  (~30s per charger on Apple Silicon)")
            results = await train_anomaly_models(TRAINED_IDS)
            for cp, status in results.items():
                marker = "✓" if status == "ok" else "✗"
                print(f"  {marker} {cp}: {status}")

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  ✓ Demo dataset ready")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  Login:    {args.demo_email}")
        print(f"  Password: {args.demo_password}")
        print(f"  URL:      http://localhost:5173/login")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--full", action="store_true",
                   help="Run the all-in-one demo seeder")
    p.add_argument("--demo-org", default="Demo CPO")
    p.add_argument("--demo-email", default="demo@democpo.in")
    p.add_argument("--demo-password", default="demo123")
    p.add_argument("--skip-training", action="store_true",
                   help="Skip LSTM training (much faster re-seed)")

    # CSV mode
    p.add_argument("--api", default=DEFAULT_API)
    p.add_argument("--gateway", default=GATEWAY_BASE)
    p.add_argument("--org")
    p.add_argument("--email")
    p.add_argument("--password")
    p.add_argument("--full-name", default="Admin")
    p.add_argument("--csv", help="CSV file for original onboarding mode")
    p.add_argument("--webhook", default=None)

    args = p.parse_args()

    if args.full:
        asyncio.run(run_full(args))
        return

    if not (args.org and args.email and args.password and args.csv):
        p.error("Either pass --full, or supply --org --email --password --csv "
                "for CSV onboarding mode")
    run_csv_mode(args)


if __name__ == "__main__":
    main()
