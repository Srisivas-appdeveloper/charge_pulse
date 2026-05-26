"""Pull feature vectors out of TimescaleDB and shape them into training sequences.

For one charger, we look at the last N days of `feature_vectors`. We then slide
a window of `seq_len` (default 96 = 24h at 15-min cadence) across the series to
produce training samples shaped (n_samples, seq_len, 24).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg
import numpy as np


async def load_feature_matrix(
    pool: asyncpg.Pool, cp_id: str, days: int = 14,
) -> np.ndarray:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, features FROM feature_vectors
            WHERE cp_id = $1 AND time >= $2
            ORDER BY time
            """,
            cp_id, cutoff,
        )
    if not rows:
        return np.empty((0, 24), dtype=np.float32)
    return np.array([list(r["features"]) for r in rows], dtype=np.float32)


def windowize(features: np.ndarray, seq_len: int = 96) -> np.ndarray:
    """Slide a window of `seq_len` over (T, n_features) → (T-seq_len+1, seq_len, n_features)."""
    if features.shape[0] < seq_len:
        return np.empty((0, seq_len, features.shape[1] if features.size else 24),
                        dtype=np.float32)
    n = features.shape[0] - seq_len + 1
    out = np.lib.stride_tricks.sliding_window_view(
        features, window_shape=seq_len, axis=0
    )
    # sliding_window_view returns (T-seq+1, n_features, seq_len). Swap axes.
    return np.ascontiguousarray(out.transpose(0, 2, 1).astype(np.float32))
