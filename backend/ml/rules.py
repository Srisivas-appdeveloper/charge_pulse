"""Rule-based alert engine (Phase 1 — ships before ML is trained).

Each rule evaluates a 24-feature vector dict and either fires (returns an
incident draft) or stays silent (returns None). Rule names match Section 8.4.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Rule:
    name: str
    severity: str
    failure_type: str
    title: str
    condition: Callable[[dict], bool]


def _gt(field: str, threshold: float) -> Callable[[dict], bool]:
    return lambda f: f.get(field, 0) > threshold


def _ge(field: str, threshold: float) -> Callable[[dict], bool]:
    return lambda f: f.get(field, 0) >= threshold


RULES: tuple[Rule, ...] = (
    Rule(
        "heartbeat_missing", "high", "communication_loss",
        "Charger stopped responding",
        _gt("heartbeat_gap_max_sec", 300),
    ),
    Rule(
        "faulted_state", "critical", "connector_fault",
        "Charger in faulted state",
        _gt("time_in_faulted_pct", 0.10),
    ),
    Rule(
        "voltage_low", "high", "power_supply",
        "Low voltage detected",
        lambda f: 0 < f.get("min_voltage_v", 0) < 200,
    ),
    Rule(
        "voltage_high", "high", "power_supply",
        "High voltage spike detected",
        _gt("max_voltage_v", 260),
    ),
    Rule(
        "session_failures_spike", "medium", "connector_fault",
        "High session failure rate",
        lambda f: f.get("session_completion_rate", 1.0) < 0.70
        and f.get("sessions_started", 0) >= 3,
    ),
    Rule(
        "power_instability", "medium", "power_supply",
        "Unstable power delivery",
        lambda f: f.get("std_power_kw", 0) > 5.0 and f.get("avg_power_kw", 0) > 1.0,
    ),
    Rule(
        "frequent_reboots", "high", "firmware_crash",
        "Charger rebooting repeatedly",
        _ge("ws_reconnections", 3),
    ),
    Rule(
        "zero_sessions_during_peak", "low", "unknown",
        "No sessions during peak hours",
        lambda f: f.get("sessions_started", 0) == 0 and f.get("hour_of_day_sin", 0) > 0.5,
    ),
)


def evaluate(features: dict) -> list[Rule]:
    """Returns every rule that fires on the given feature dict."""
    fired = []
    for rule in RULES:
        try:
            if rule.condition(features):
                fired.append(rule)
        except (KeyError, TypeError):
            continue
    return fired
