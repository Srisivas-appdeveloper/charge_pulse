"""XGBoost failure-type classifier (Section 8.2).

Predicts which failure category an anomaly belongs to. Trained on labelled
incidents — uses `confirmed_failure_type` when set (human-verified) and falls
back to `failure_type` (rule-inferred) for the cold-start.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xgboost as xgb

FAILURE_TYPES: tuple[str, ...] = (
    "power_supply",
    "connector_fault",
    "communication_loss",
    "payment_system",
    "firmware_crash",
    "thermal_overload",
    "ground_fault",
    "unknown",
)
_TYPE_TO_IDX = {t: i for i, t in enumerate(FAILURE_TYPES)}


def label_to_idx(label: str) -> int:
    return _TYPE_TO_IDX.get(label, _TYPE_TO_IDX["unknown"])


def idx_to_label(i: int) -> str:
    return FAILURE_TYPES[i]


class FailureClassifier:
    def __init__(self):
        self.model: xgb.XGBClassifier | None = None
        self._trained = False
        # XGBoost requires contiguous class labels. When training data only
        # covers a subset of failure types, we remap to {0..k-1} and remember
        # the original labels so predict() returns proper names.
        self._classes: np.ndarray | None = None

    def _make_model(self, n_class: int) -> xgb.XGBClassifier:
        return xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            objective="multi:softprob" if n_class > 2 else "binary:logistic",
            num_class=n_class if n_class > 2 else None,
            eval_metric="mlogloss" if n_class > 2 else "logloss",
            subsample=0.8,
            colsample_bytree=0.8,
            tree_method="hist",
        )

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight=None) -> dict:
        self._classes = np.unique(y)
        if len(self._classes) < 2:
            raise ValueError(
                f"need ≥2 distinct failure types to train; got {self._classes.tolist()}"
            )
        # Remap original labels to 0..k-1.
        label_to_dense = {orig: i for i, orig in enumerate(self._classes.tolist())}
        y_dense = np.array([label_to_dense[int(v)] for v in y], dtype=np.int32)
        self.model = self._make_model(len(self._classes))
        self.model.fit(X, y_dense, sample_weight=sample_weight)
        self._trained = True
        preds = self.model.predict(X)
        return {
            "train_accuracy": float((preds == y_dense).mean()),
            "n_samples": int(len(y_dense)),
            "n_classes": int(len(self._classes)),
            "covered_failure_types": [idx_to_label(int(c)) for c in self._classes],
        }

    def predict(self, features: np.ndarray) -> dict:
        if not self._trained or self.model is None or self._classes is None:
            raise RuntimeError("classifier not trained")
        if features.ndim == 1:
            features = features.reshape(1, -1)
        probs = self.model.predict_proba(features)[0]
        ranked = sorted(enumerate(probs), key=lambda x: x[1], reverse=True)
        top_orig_idx = int(self._classes[ranked[0][0]])
        return {
            "predicted_failure": idx_to_label(top_orig_idx),
            "confidence": float(ranked[0][1]),
            "all_probabilities": {
                idx_to_label(int(self._classes[i])): float(p)
                for i, p in enumerate(probs)
            },
        }

    def save(self, path: str | Path) -> None:
        if self.model is None or self._classes is None:
            raise RuntimeError("classifier not trained")
        # Use the underlying Booster's save (bypasses sklearn wrapper changes
        # between xgboost / scikit-learn versions).
        self.model.get_booster().save_model(str(path))
        meta_path = Path(str(path) + ".meta.json")
        meta_path.write_text(json.dumps({"classes": self._classes.tolist()}))

    def load(self, path: str | Path) -> None:
        meta = json.loads(Path(str(path) + ".meta.json").read_text())
        self._classes = np.array(meta["classes"], dtype=np.int64)
        self.model = self._make_model(len(self._classes))
        booster = xgb.Booster()
        booster.load_model(str(path))
        self.model._Booster = booster
        self.model._n_classes = len(self._classes)  # type: ignore[attr-defined]
        self._trained = True
