"""Feature extraction unit tests — pure functions, no DB needed."""
from datetime import datetime, timedelta, timezone

from ml.features import FEATURE_NAMES, extract, to_dict


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def test_feature_vector_has_exactly_24_dims():
    fv = extract(
        cp_id="X", window_start=_now(), window_end=_now() + timedelta(minutes=15),
        events=[], sessions=[],
    )
    assert len(FEATURE_NAMES) == 24
    assert fv.values.shape == (24,)


def test_empty_window_yields_neutral_vector():
    fv = extract(
        cp_id="X", window_start=_now(), window_end=_now() + timedelta(minutes=15),
        events=[], sessions=[],
    )
    d = to_dict(fv)
    assert d["sessions_started"] == 0
    assert d["session_completion_rate"] == 1.0  # vacuously true
    assert d["heartbeat_count"] == 0
    assert d["error_code_count"] == 0
    assert d["status_transitions"] == 0


def test_faulted_status_drives_faulted_pct():
    start = _now()
    end = start + timedelta(minutes=15)
    # Faulted halfway through the window
    events = [
        {"time": start + timedelta(minutes=8), "event_type": "status",
         "connector_id": 1,
         "payload": {"status": "Faulted", "error_code": "GroundFailure"}},
    ]
    fv = extract(cp_id="X", window_start=start, window_end=end, events=events, sessions=[])
    d = to_dict(fv)
    # ~7 min faulted / 15 min total
    assert 0.4 < d["time_in_faulted_pct"] < 0.6
    assert d["error_code_count"] == 1
    assert d["unique_error_codes"] == 1


def test_session_completion_rate():
    start = _now()
    end = start + timedelta(minutes=15)
    sessions = [
        {"started_at": start, "stopped_at": start + timedelta(minutes=5),
         "energy_kwh": 5.0, "duration_min": 5.0, "stop_reason": "EVDisconnected"},
        {"started_at": start, "stopped_at": start + timedelta(minutes=3),
         "energy_kwh": 2.0, "duration_min": 3.0, "stop_reason": "PowerLoss"},
    ]
    fv = extract(cp_id="X", window_start=start, window_end=end, events=[], sessions=sessions)
    d = to_dict(fv)
    assert d["sessions_started"] == 2
    assert d["sessions_completed"] == 1
    assert d["sessions_failed"] == 1
    assert d["session_completion_rate"] == 0.5
