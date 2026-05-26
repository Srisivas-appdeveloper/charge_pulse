"""LSTM Autoencoder per Section 8.1.

Architecture:
  Input:        (batch, seq_len, 24)
  Encoder LSTM: 24 → 64 hidden, 2 layers, dropout 0.2
  Encoder FC:   64 → 32  (latent)
  Decoder FC:   32 → 64  (expanded to seq_len timesteps)
  Decoder LSTM: 64 → 64 hidden, 2 layers, dropout 0.2
  Output FC:    64 → 24

High reconstruction error on the latest window ⇒ anomaly.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class LSTMAutoencoder(nn.Module):
    def __init__(
        self,
        n_features: int = 24,
        hidden_dim: int = 64,
        latent_dim: int = 32,
        n_layers: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.n_features = n_features
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.n_layers = n_layers

        self.encoder_lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.encoder_fc = nn.Linear(hidden_dim, latent_dim)

        self.decoder_fc = nn.Linear(latent_dim, hidden_dim)
        self.decoder_lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.output_fc = nn.Linear(hidden_dim, n_features)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.encoder_lstm(x)
        return self.encoder_fc(hidden[-1])

    def decode(self, latent: torch.Tensor, seq_len: int) -> torch.Tensor:
        h = self.decoder_fc(latent)
        decoder_input = h.unsqueeze(1).repeat(1, seq_len, 1)
        decoded, _ = self.decoder_lstm(decoder_input)
        return self.output_fc(decoded)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encode(x)
        return self.decode(latent, x.size(1))


class AnomalyScorer:
    """Production-time scoring wrapper. Stateless beyond the model+normalisation."""

    def __init__(
        self,
        model: LSTMAutoencoder,
        threshold: float,
        feat_mean: torch.Tensor,
        feat_std: torch.Tensor,
    ):
        self.model = model.eval()
        self.threshold = float(threshold)
        self.feat_mean = feat_mean
        # Avoid divide-by-zero
        self.feat_std = torch.where(feat_std < 1e-6, torch.ones_like(feat_std), feat_std)

    @torch.no_grad()
    def score(self, sequence: torch.Tensor) -> dict:
        """sequence: (seq_len, n_features) or (1, seq_len, n_features)."""
        if sequence.dim() == 2:
            sequence = sequence.unsqueeze(0)
        normed = (sequence - self.feat_mean) / self.feat_std
        recon = self.model(normed)
        errors = (normed - recon).pow(2).squeeze(0)  # (seq_len, n_features)
        per_window = errors.mean(dim=1)  # (seq_len,)
        latest_error = float(per_window[-1].item())
        feature_errors = errors[-1].tolist()
        ranked = sorted(
            range(len(feature_errors)),
            key=lambda i: feature_errors[i],
            reverse=True,
        )
        return {
            "anomaly_score": latest_error,
            "is_anomaly": latest_error > self.threshold,
            "feature_errors": feature_errors,
            "top_anomalous_feature_indices": ranked[:5],
        }
