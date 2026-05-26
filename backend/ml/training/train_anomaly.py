"""Per-charger LSTM autoencoder training (Section 8.1).

Run:
    python -m ml.training.train_anomaly --cp_id CP001 [--days 14] [--epochs 50]

Writes the trained model to MODEL_STORE_PATH and registers it in `ml_models`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import asyncpg
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from app.config import get_settings
from app.db.session import create_asyncpg_pool
from ml.models.anomaly_detector import LSTMAutoencoder
from ml.training.data_loader import load_feature_matrix, windowize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("chargepulse.train_anomaly")

SEQ_LEN = 96  # 24 hours at 15-min cadence
BATCH_SIZE = 32
DEFAULT_EPOCHS = 50
PATIENCE = 10
LR = 1e-3
WEIGHT_DECAY = 1e-5


async def train(cp_id: str, days: int, epochs: int) -> None:
    settings = get_settings()
    pool = await create_asyncpg_pool()
    try:
        matrix = await load_feature_matrix(pool, cp_id, days=days)
        log.info("Loaded %d feature vectors for cp=%s (last %dd)",
                 len(matrix), cp_id, days)
        if len(matrix) < SEQ_LEN + 10:
            raise RuntimeError(
                f"Need at least {SEQ_LEN + 10} feature vectors to train; have {len(matrix)}. "
                "Run scripts/generate_training_data.py first or accumulate more real data."
            )

        windows = windowize(matrix, seq_len=SEQ_LEN)
        log.info("Built %d training windows of shape %s", len(windows), windows.shape)

        # Normalize using full-matrix stats (not per-window) so training and
        # inference share the same scaler.
        feat_mean = matrix.mean(axis=0)
        feat_std = matrix.std(axis=0)
        feat_std = np.where(feat_std < 1e-6, 1.0, feat_std)
        normed = (windows - feat_mean) / feat_std

        # 80/20 split (chronological — last 20% is val).
        split = int(0.8 * len(normed))
        train_arr = torch.from_numpy(normed[:split])
        val_arr = torch.from_numpy(normed[split:])
        train_dl = DataLoader(
            TensorDataset(train_arr), batch_size=BATCH_SIZE, shuffle=True,
        )
        val_dl = DataLoader(TensorDataset(val_arr), batch_size=BATCH_SIZE)

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        model = LSTMAutoencoder().to(device)
        opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        loss_fn = torch.nn.MSELoss()

        best_val = float("inf")
        best_state = None
        patience = 0
        for epoch in range(1, epochs + 1):
            model.train()
            train_losses = []
            for (batch,) in train_dl:
                batch = batch.to(device)
                opt.zero_grad()
                recon = model(batch)
                loss = loss_fn(recon, batch)
                loss.backward()
                opt.step()
                train_losses.append(loss.item())

            model.eval()
            with torch.no_grad():
                val_losses = []
                for (batch,) in val_dl:
                    batch = batch.to(device)
                    recon = model(batch)
                    val_losses.append(loss_fn(recon, batch).item())
            train_loss = float(np.mean(train_losses))
            val_loss = float(np.mean(val_losses)) if val_losses else train_loss
            log.info("epoch %d: train=%.5f val=%.5f", epoch, train_loss, val_loss)

            if val_loss < best_val - 1e-5:
                best_val = val_loss
                best_state = {k: v.clone().detach().cpu() for k, v in model.state_dict().items()}
                patience = 0
            else:
                patience += 1
                if patience >= PATIENCE:
                    log.info("Early stopping at epoch %d", epoch)
                    break

        assert best_state is not None
        model.load_state_dict(best_state)

        # Threshold = 95th percentile of per-window reconstruction error on training set.
        model.eval()
        with torch.no_grad():
            all_train = torch.from_numpy(normed[:split]).to(device)
            recon = model(all_train)
            errs = ((all_train - recon) ** 2).mean(dim=(1, 2)).cpu().numpy()
        threshold = float(np.percentile(errs, 95))
        log.info("Training error p50=%.5f p95=%.5f (threshold)", float(np.median(errs)), threshold)

        # Persist .pt + metadata. ml_models row is the source of truth for inference.
        store_dir = Path(settings.model_store_path)
        store_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        rel = f"anomaly_{cp_id}_{ts}.pt"
        path = store_dir / rel
        torch.save({
            "state_dict": best_state,
            "feat_mean": feat_mean.tolist(),
            "feat_std": feat_std.tolist(),
            "threshold": threshold,
            "trained_at": ts,
            "samples": len(normed),
            "seq_len": SEQ_LEN,
        }, path)
        log.info("Saved model to %s", path)

        async with pool.acquire() as conn:
            # Deactivate previous active models for this cp_id.
            await conn.execute(
                "UPDATE ml_models SET is_active = false "
                "WHERE cp_id = $1 AND model_type = 'anomaly_detector'",
                cp_id,
            )
            await conn.execute(
                """
                INSERT INTO ml_models
                  (cp_id, model_type, version, training_samples, metrics,
                   model_path, is_active)
                VALUES ($1, 'anomaly_detector',
                  COALESCE((SELECT MAX(version) FROM ml_models
                            WHERE cp_id = $1 AND model_type = 'anomaly_detector'), 0) + 1,
                  $2, $3, $4, true)
                """,
                cp_id, len(normed),
                json.dumps({"val_mse": best_val, "threshold": threshold}),
                rel,
            )
        log.info("ml_models row created for cp=%s", cp_id)
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cp_id", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    args = parser.parse_args()
    asyncio.run(train(args.cp_id, args.days, args.epochs))


if __name__ == "__main__":
    main()
