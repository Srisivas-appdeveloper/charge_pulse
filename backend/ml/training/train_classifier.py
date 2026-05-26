"""Train the XGBoost failure-type classifier on labelled incidents.

For each incident with a known failure type, find the feature_vector closest
in time (≤30 min before detection) and use that 24-dim vector + the rule-derived
anomaly_score as the training row.

Run:
    python -m ml.training.train_classifier [--min-samples 50]

Registers the trained model in `ml_models` and writes the booster to
`MODEL_STORE_PATH/failure_classifier_<ts>.xgb`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.db.session import create_asyncpg_pool
from ml.models.failure_classifier import FailureClassifier, label_to_idx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.train_classifier")


async def build_dataset(pool) -> tuple[np.ndarray, np.ndarray]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              i.detected_at,
              COALESCE(i.confirmed_failure_type, i.failure_type) AS label,
              i.anomaly_score,
              (SELECT features FROM feature_vectors
                WHERE cp_id = i.cp_id AND time <= i.detected_at
                ORDER BY time DESC LIMIT 1) AS features
            FROM incidents i
            WHERE COALESCE(i.confirmed_failure_type, i.failure_type) IS NOT NULL
            """,
        )
    X, y = [], []
    skipped = 0
    for r in rows:
        if r["features"] is None:
            skipped += 1; continue
        feats = list(r["features"])
        feats.append(float(r["anomaly_score"] or 0.0))
        X.append(feats)
        y.append(label_to_idx(r["label"]))
    log.info("Built dataset: %d samples (skipped %d incidents missing features)",
             len(X), skipped)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


async def main(min_samples: int) -> None:
    settings = get_settings()
    pool = await create_asyncpg_pool()
    try:
        X, y = await build_dataset(pool)
        if len(X) < min_samples:
            log.warning(
                "Only %d labelled samples — need ≥%d to train. Run pilots longer "
                "or label more incidents via the dashboard.", len(X), min_samples,
            )
            return

        clf = FailureClassifier()
        metrics = clf.fit(X, y)
        log.info("Trained: %s", metrics)

        store = Path(settings.model_store_path)
        store.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        rel = f"failure_classifier_{ts}.xgb"
        clf.save(store / rel)
        log.info("Saved booster to %s", store / rel)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ml_models SET is_active = false WHERE model_type = 'failure_classifier'",
            )
            await conn.execute(
                """
                INSERT INTO ml_models
                  (cp_id, model_type, version, training_samples, metrics, model_path, is_active)
                VALUES (NULL, 'failure_classifier',
                  COALESCE((SELECT MAX(version) FROM ml_models WHERE model_type = 'failure_classifier'), 0) + 1,
                  $1, $2, $3, true)
                """,
                int(metrics["n_samples"]), json.dumps(metrics), rel,
            )
        log.info("ml_models row created")
    finally:
        await pool.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-samples", type=int, default=20,
                    help="minimum labelled samples required (spec recommends 500 for production)")
    args = ap.parse_args()
    asyncio.run(main(args.min_samples))
