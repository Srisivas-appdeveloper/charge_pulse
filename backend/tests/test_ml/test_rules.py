"""Rule engine tests — pure functions over feature dicts."""
from ml import rules


BASE = {n: 0 for n in [
    "sessions_started", "sessions_completed", "sessions_failed",
    "avg_session_duration_min", "avg_energy_delivered_kwh", "session_completion_rate",
    "avg_power_kw", "std_power_kw", "max_voltage_v", "min_voltage_v",
    "avg_current_a", "power_factor",
    "status_transitions", "time_in_faulted_pct", "time_in_available_pct",
    "time_in_unavailable_pct", "error_code_count", "unique_error_codes",
    "heartbeat_count", "heartbeat_gap_max_sec", "heartbeat_gap_std_sec",
    "ws_reconnections", "hour_of_day_sin", "day_of_week_sin",
]}
BASE["session_completion_rate"] = 1.0
BASE["power_factor"] = 1.0


def test_normal_vector_fires_no_rules():
    fired = rules.evaluate(BASE | {"time_in_available_pct": 1.0, "heartbeat_count": 150})
    assert fired == []


def test_heartbeat_gap_triggers_communication_loss():
    fired = rules.evaluate(BASE | {"heartbeat_gap_max_sec": 400})
    names = [r.name for r in fired]
    assert "heartbeat_missing" in names
    rule = next(r for r in fired if r.name == "heartbeat_missing")
    assert rule.severity == "high"
    assert rule.failure_type == "communication_loss"


def test_faulted_pct_above_threshold_triggers_critical():
    fired = rules.evaluate(BASE | {"time_in_faulted_pct": 0.5})
    rule = next(r for r in fired if r.name == "faulted_state")
    assert rule.severity == "critical"
    assert rule.failure_type == "connector_fault"


def test_voltage_low_and_high_both_classify_as_power_supply():
    low = rules.evaluate(BASE | {"min_voltage_v": 180})
    high = rules.evaluate(BASE | {"max_voltage_v": 270})
    assert any(r.name == "voltage_low" for r in low)
    assert any(r.name == "voltage_high" for r in high)


def test_frequent_reboots_at_three():
    assert any(r.name == "frequent_reboots" for r in rules.evaluate(BASE | {"ws_reconnections": 3}))
    assert not any(r.name == "frequent_reboots" for r in rules.evaluate(BASE | {"ws_reconnections": 2}))


def test_session_failure_spike_needs_min_attempts():
    """Spec: completion < 0.7 AND sessions_started >= 3."""
    near = BASE | {"session_completion_rate": 0.5, "sessions_started": 2}
    far = BASE | {"session_completion_rate": 0.5, "sessions_started": 3}
    assert not any(r.name == "session_failures_spike" for r in rules.evaluate(near))
    assert any(r.name == "session_failures_spike" for r in rules.evaluate(far))
