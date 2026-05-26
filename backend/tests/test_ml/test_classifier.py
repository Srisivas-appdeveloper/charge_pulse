"""XGBoost failure classifier sanity test on synthetic data."""
import numpy as np

from ml.models.failure_classifier import FAILURE_TYPES, FailureClassifier, label_to_idx


def _synth(n_per_class: int = 30):
    """Two well-separated clusters per failure type so a small XGBoost overfits cleanly."""
    rng = np.random.default_rng(0)
    X, y = [], []
    for label_idx in range(len(FAILURE_TYPES)):
        # 25 features (24 + anomaly_score). Shift centroid per class.
        centroid = np.zeros(25); centroid[label_idx % 25] = 5.0
        X.append(rng.normal(centroid, 0.4, size=(n_per_class, 25)))
        y.extend([label_idx] * n_per_class)
    return np.vstack(X).astype(np.float32), np.array(y, dtype=np.int32)


def test_classifier_fits_and_predicts():
    X, y = _synth()
    clf = FailureClassifier()
    metrics = clf.fit(X, y)
    assert metrics["train_accuracy"] >= 0.9
    pred = clf.predict(X[0])
    assert pred["predicted_failure"] in FAILURE_TYPES
    assert 0.0 <= pred["confidence"] <= 1.0
    assert abs(sum(pred["all_probabilities"].values()) - 1.0) < 1e-4


def test_label_to_idx_unknown_fallback():
    assert label_to_idx("not_a_real_failure_type") == FAILURE_TYPES.index("unknown")
