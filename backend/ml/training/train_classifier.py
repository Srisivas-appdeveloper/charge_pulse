"""Train the XGBoost failure-type classifier on labelled incidents (Section 8.2).

For each incident with a known failure type, find the feature_vector closest
in time (≤30 min before detection) and use that 24-dim vector + the rule-derived
anomaly_score as the training row (25 features total).

Run:
    python -m ml.training.train_classifier [--min-samples 50]

Registers the trained model in `ml_models` and writes the booster to
`MODEL_STORE_PATH/failure_classifier_v1.xgb`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold

from app.config import get_settings
from app.db.session import create_asyncpg_pool
from ml.models.failure_classifier import (
    FailureClassifier,
    idx_to_label,
    label_to_idx,
)

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
                WHERE cp_id = i.cp_id
                  AND time <= i.detected_at
                  AND time >= i.detected_at - INTERVAL '30 minutes'
                ORDER BY time DESC LIMIT 1) AS features
            FROM incidents i
            WHERE i.confirmed_failure_type IS NOT NULL
            """,
        )
    X, y = [], []
    skipped = 0
    for r in rows:
        if r["features"] is None:
            skipped += 1
            continue
        feats = list(r["features"])
        feats.append(float(r["anomaly_score"] or 0.0))
        X.append(feats)
        y.append(label_to_idx(r["label"]))
    log.info(
        "Built dataset: %d samples (skipped %d incidents missing features)",
        len(X), skipped,
    )
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def _cross_validate(X: np.ndarray, y: np.ndarray) -> dict:
    """5-fold stratified CV. Returns mean accuracy, per-class F1, and a
    pooled confusion matrix across folds."""
    classes = np.unique(y)
    n_splits = min(5, int(np.min(np.bincount(y)[np.bincount(y) > 0])))
    if n_splits < 2:
        log.warning("Too few samples per class for CV (min=%d); skipping CV.", n_splits)
        return {"cv_skipped": True}

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    fold_acc: list[float] = []
    y_true_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []
    for fold, (tr, va) in enumerate(skf.split(X, y), start=1):
        clf = FailureClassifier()
        clf.fit(X[tr], y[tr])
        # FailureClassifier remaps to dense labels internally; predict() returns
        # the failure-type *name*. Convert back to the original index for metrics.
        preds_idx = []
        for row in X[va]:
            out = clf.predict(row)
            preds_idx.append(label_to_idx(out["predicted_failure"]))
        preds = np.array(preds_idx, dtype=np.int32)
        truth = y[va]
        acc = float((preds == truth).mean())
        fold_acc.append(acc)
        y_true_all.append(truth)
        y_pred_all.append(preds)
        log.info("fold %d/%d acc=%.3f", fold, n_splits, acc)

    y_true = np.concatenate(y_true_all)
    y_pred = np.concatenate(y_pred_all)
    f1_per_class = f1_score(
        y_true, y_pred, labels=classes, average=None, zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=classes)

    return {
        "cv_splits": n_splits,
        "mean_accuracy": float(np.mean(fold_acc)),
        "fold_accuracies": [float(a) for a in fold_acc],
        "f1_per_class": {
            idx_to_label(int(c)): float(f) for c, f in zip(classes, f1_per_class)
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": [idx_to_label(int(c)) for c in classes],
    }


def _print_summary(cv: dict) -> None:
    if cv.get("cv_skipped"):
        print("Cross-validation skipped (too few samples per class).")
        return
    print(f"\n=== 5-fold CV ({cv['cv_splits']} splits) ===")
    print(f"Mean accuracy: {cv['mean_accuracy']:.3f}")
    print("F1 per class:")
    for k, v in cv["f1_per_class"].items():
        print(f"  {k:22s} {v:.3f}")
    print("\nConfusion matrix:")
    labels = cv["confusion_matrix_labels"]
    header = "actual \\ pred".ljust(22) + " ".join(l[:10].rjust(10) for l in labels)
    print(header)
    for label, row in zip(labels, cv["confusion_matrix"]):
        print(label.ljust(22) + " ".join(str(v).rjust(10) for v in row))


async def main(min_samples: int) -> None:
    settings = get_settings()
    pool = await create_asyncpg_pool()
    try:
        X, y = await build_dataset(pool)
        if len(X) < min_samples:
            print(
                f"Not enough labeled data yet (need {min_samples}+, have {len(X)}). "
                "Using rule-based classification until more data."
            )
            return

        cv = _cross_validate(X, y)
        _print_summary(cv)

        clf = FailureClassifier()
        fit_metrics = clf.fit(X, y)
        log.info("Final fit on full dataset: %s", fit_metrics)

        store = Path(settings.model_store_path)
        store.mkdir(parents=True, exist_ok=True)
        rel = "failure_classifier_v1.xgb"
        clf.save(store / rel)
        log.info("Saved booster to %s", store / rel)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ml_models SET is_active = false "
                "WHERE model_type = 'failure_classifier'",
            )
            await conn.execute(
                """
                INSERT INTO ml_models
                  (cp_id, model_type, version, training_samples, metrics,
                   model_path, is_active)
                VALUES (NULL, 'failure_classifier',
                  COALESCE((SELECT MAX(version) FROM ml_models
                            WHERE model_type = 'failure_classifier'), 0) + 1,
                  $1, $2, $3, true)
                """,
                int(fit_metrics["n_samples"]),
                json.dumps({**fit_metrics, **cv}),
                rel,
            )
        log.info("ml_models row created")
    finally:
        await pool.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--min-samples", type=int, default=50,
        help="minimum labelled samples required (spec: 50+)",
    )
    args = ap.parse_args()
    asyncio.run(main(args.min_samples))
