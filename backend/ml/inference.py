"""Model store + real-time inference helpers used by inference_worker.

Caches loaded `AnomalyScorer`s per (cp_id, model_path). When a new model is
trained, its row in `ml_models` gets `is_active=true` and an incremented
`version` — we invalidate the cache by checking version on each load.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
import torch

from app.config import get_settings
from ml.models.anomaly_detector import AnomalyScorer, LSTMAutoencoder

log = logging.getLogger("chargepulse.inference")


@dataclass
class CachedScorer:
    version: int
    scorer: AnomalyScorer


_cache: dict[str, CachedScorer] = {}


async def load_active_model(pool: asyncpg.Pool, cp_id: str) -> AnomalyScorer | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT version, model_path, metrics
            FROM ml_models
            WHERE cp_id = $1 AND model_type = 'anomaly_detector' AND is_active = true
            ORDER BY version DESC LIMIT 1
            """,
            cp_id,
        )
    if not row:
        return None

    cached = _cache.get(cp_id)
    if cached and cached.version == row["version"]:
        return cached.scorer

    settings = get_settings()
    path = Path(settings.model_store_path) / row["model_path"]
    if not path.exists():
        log.warning("Model file missing for cp=%s path=%s", cp_id, path)
        return None
    blob = torch.load(path, map_location="cpu", weights_only=False)
    model = LSTMAutoencoder()
    model.load_state_dict(blob["state_dict"])
    scorer = AnomalyScorer(
        model=model,
        threshold=blob["threshold"],
        feat_mean=torch.tensor(blob["feat_mean"], dtype=torch.float32),
        feat_std=torch.tensor(blob["feat_std"], dtype=torch.float32),
    )
    _cache[cp_id] = CachedScorer(version=row["version"], scorer=scorer)
    log.info("Loaded anomaly model cp=%s version=%d threshold=%.5f",
             cp_id, row["version"], scorer.threshold)
    return scorer


async def score_latest_window(
    pool: asyncpg.Pool, scorer: AnomalyScorer, cp_id: str, seq_len: int = 96,
) -> dict | None:
    """Read the most recent `seq_len` feature vectors for this charger and score
    the latest one."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, features FROM feature_vectors
            WHERE cp_id = $1
            ORDER BY time DESC LIMIT $2
            """,
            cp_id, seq_len,
        )
    if len(rows) < 2:
        return None
    # Most-recent-first → reverse to chronological
    rows = list(reversed(rows))
    matrix = torch.tensor([list(r["features"]) for r in rows], dtype=torch.float32)
    # Pad with the earliest row if we don't have a full window yet.
    if matrix.size(0) < seq_len:
        pad = matrix[0:1].repeat(seq_len - matrix.size(0), 1)
        matrix = torch.cat([pad, matrix], dim=0)
    result = scorer.score(matrix)
    result["scored_at"] = rows[-1]["time"]
    return result


async def write_score(
    pool: asyncpg.Pool, cp_id: str, scored_at, anomaly_score: float, is_anomaly: bool,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE feature_vectors
               SET anomaly_score = $1, is_anomaly = $2
             WHERE cp_id = $3 AND time = $4
            """,
            anomaly_score, is_anomaly, cp_id, scored_at,
        )
