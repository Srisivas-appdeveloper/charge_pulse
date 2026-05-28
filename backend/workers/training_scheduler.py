"""Nightly + weekly retraining scheduler (Section 8.3).

Schedules:
  * Daily 02:00 — for each charger with ≥14 days of feature data and no model
    trained in the last 7 days, retrain the LSTM autoencoder. Activate the
    new model only if val_loss improves on the currently active one.
  * Sunday 03:00 — retrain the global XGBoost failure classifier on all
    labelled incidents (≥50 required).

Run:
    python -m workers.training_scheduler
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import create_asyncpg_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.training_scheduler")

MIN_DAYS_OF_DATA = 14
RETRAIN_COOLDOWN_DAYS = 7


async def _candidates_for_retrain(pool: asyncpg.Pool) -> list[str]:
    cutoff_data = datetime.now(timezone.utc) - timedelta(days=MIN_DAYS_OF_DATA)
    cutoff_retrain = datetime.now(timezone.utc) - timedelta(days=RETRAIN_COOLDOWN_DAYS)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fv.cp_id
              FROM feature_vectors fv
             GROUP BY fv.cp_id
            HAVING MIN(fv.time) <= $1
               AND NOT EXISTS (
                 SELECT 1 FROM ml_models m
                  WHERE m.cp_id = fv.cp_id
                    AND m.model_type = 'anomaly_detector'
                    AND m.created_at >= $2
               )
            """,
            cutoff_data, cutoff_retrain,
        )
    return [r["cp_id"] for r in rows]


async def _current_val_loss(pool: asyncpg.Pool, cp_id: str) -> float | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT metrics FROM ml_models
             WHERE cp_id = $1 AND model_type = 'anomaly_detector' AND is_active = true
             ORDER BY version DESC LIMIT 1
            """,
            cp_id,
        )
    if not row or not row["metrics"]:
        return None
    try:
        return float(json.loads(row["metrics"]).get("val_mse"))
    except (TypeError, ValueError):
        return None


def _run_anomaly_training(cp_id: str) -> int:
    """Spawns the training script as a subprocess. The script handles its own
    DB persistence + model_store write."""
    return subprocess.call(
        [sys.executable, "-m", "ml.training.train_anomaly", "--cp_id", cp_id]
    )


def _run_classifier_training() -> int:
    return subprocess.call(
        [sys.executable, "-m", "ml.training.train_classifier", "--min-samples", "50"]
    )


async def _maybe_demote_worse_model(pool: asyncpg.Pool, cp_id: str, prev_val: float | None) -> None:
    """train_anomaly.py always activates its new model. If the previous one was
    better, revert by reactivating it."""
    if prev_val is None:
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, version, metrics, is_active
              FROM ml_models
             WHERE cp_id = $1 AND model_type = 'anomaly_detector'
             ORDER BY version DESC LIMIT 2
            """,
            cp_id,
        )
    if len(rows) < 2:
        return
    new_row, old_row = rows[0], rows[1]
    try:
        new_val = float(json.loads(new_row["metrics"]).get("val_mse"))
    except (TypeError, ValueError):
        return
    if new_val < prev_val:
        log.info("cp=%s new model better (val=%.5f < %.5f) — keep new", cp_id, new_val, prev_val)
        return
    log.info(
        "cp=%s new model worse (val=%.5f >= %.5f) — reverting to v%d",
        cp_id, new_val, prev_val, old_row["version"],
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE ml_models SET is_active = false WHERE id = $1", new_row["id"],
        )
        await conn.execute(
            "UPDATE ml_models SET is_active = true  WHERE id = $1", old_row["id"],
        )


async def nightly_retrain() -> None:
    log.info("Nightly retrain — scanning candidates")
    pool = await create_asyncpg_pool()
    try:
        candidates = await _candidates_for_retrain(pool)
        log.info("Candidates: %d → %s", len(candidates), candidates)
        for cp_id in candidates:
            prev_val = await _current_val_loss(pool, cp_id)
            log.info("Training anomaly model cp=%s (prev val_mse=%s)", cp_id, prev_val)
            try:
                rc = await asyncio.to_thread(_run_anomaly_training, cp_id)
                if rc != 0:
                    log.warning("Training script returned rc=%d cp=%s", rc, cp_id)
                    continue
                await _maybe_demote_worse_model(pool, cp_id, prev_val)
            except Exception:
                log.exception("Training failed cp=%s", cp_id)
    finally:
        await pool.close()


async def weekly_classifier_retrain() -> None:
    log.info("Weekly classifier retrain")
    try:
        rc = await asyncio.to_thread(_run_classifier_training)
        log.info("Classifier training rc=%d", rc)
    except Exception:
        log.exception("Classifier retrain failed")


async def main() -> None:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        nightly_retrain, CronTrigger(hour=2, minute=0),
        id="nightly_retrain", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        weekly_classifier_retrain, CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_classifier_retrain", max_instances=1, coalesce=True,
    )
    scheduler.start()
    log.info("Training scheduler started — nightly 02:00 UTC, weekly Sun 03:00 UTC")
    # Run forever
    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
