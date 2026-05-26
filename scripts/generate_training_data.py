"""Generate synthetic 'normal' feature vectors for ML training.

For each charger in the DB, inserts ~14 days × 96 (15-min) = 1344 feature
vectors into `feature_vectors`. Values follow realistic distributions for a
healthy, lightly-loaded charger so the autoencoder can learn what 'normal'
looks like.

Usage:
    .venv/bin/python scripts/generate_training_data.py --cp_id CP001 --days 14
"""
import argparse
import asyncio
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import asyncpg  # noqa: E402

from app.config import get_settings  # noqa: E402


def synth_window(t: datetime, rng: np.random.Generator) -> list[float]:
    """Realistic normal feature vector for a healthy charger."""
    hour = t.hour + t.minute / 60
    # daily session pattern: peak 10-22h
    daily_factor = math.exp(-((hour - 16) ** 2) / 30)
    sessions_started = max(0, int(rng.normal(daily_factor * 2.0, 1.0)))
    completed = max(0, sessions_started - rng.integers(0, 2))
    failed = max(0, sessions_started - completed)
    avg_dur = float(rng.normal(35, 10)) if sessions_started else 0.0
    avg_energy = float(rng.normal(18, 4)) if sessions_started else 0.0
    completion = (completed / sessions_started) if sessions_started else 1.0

    avg_power = float(rng.normal(22, 3)) if sessions_started else 0.0
    std_power = float(abs(rng.normal(1.5, 0.5))) if sessions_started else 0.0
    voltage_mean = float(rng.normal(230, 3))
    max_v = voltage_mean + abs(rng.normal(5, 2))
    min_v = voltage_mean - abs(rng.normal(5, 2))
    avg_i = float(rng.normal(20, 4)) if sessions_started else 0.0
    pf = float(np.clip(rng.normal(0.95, 0.02), 0.7, 1.0))

    status_trans = sessions_started * 2 + rng.integers(0, 2)
    faulted_pct = 0.0
    available_pct = float(np.clip(rng.normal(0.95, 0.03), 0, 1))
    unavailable_pct = max(0, 1 - available_pct - faulted_pct)
    error_count = 0
    unique_errors = 0

    # ~1 heartbeat / 6s = 150/window of 15 min; cap at 150
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


async def main(cp_id: str, days: int, replace: bool):
    settings = get_settings()
    pool = await asyncpg.create_pool(
        host=settings.postgres_host, port=settings.postgres_port,
        database=settings.postgres_db, user=settings.postgres_user,
        password=settings.postgres_password,
    )
    rng = np.random.default_rng(42)
    async with pool.acquire() as conn:
        org_id = await conn.fetchval("SELECT org_id FROM chargers WHERE cp_id = $1", cp_id)
        if not org_id:
            print(f"charger {cp_id} not found"); return
        if replace:
            await conn.execute("DELETE FROM feature_vectors WHERE cp_id = $1", cp_id)
            print(f"deleted existing feature_vectors for {cp_id}")

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now = now - timedelta(minutes=now.minute % 15)
        rows = []
        for i in range(days * 96):
            t = now - timedelta(minutes=15 * i)
            rows.append((t, cp_id, org_id, synth_window(t, rng)))

        await conn.executemany(
            "INSERT INTO feature_vectors (time, cp_id, org_id, features) "
            "VALUES ($1, $2, $3, $4)",
            rows,
        )
        print(f"inserted {len(rows)} synthetic feature vectors for {cp_id}")
    await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cp_id", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--replace", action="store_true", help="wipe existing feature_vectors for this cp_id first")
    args = parser.parse_args()
    asyncio.run(main(args.cp_id, args.days, args.replace))
