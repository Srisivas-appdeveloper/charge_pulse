"""Feature extraction.

For every charger, every FEATURE_WINDOW_MINUTES window, we materialize a
24-dimensional feature vector from the raw OCPP events + session records in
that window. Vector layout matches Section 7.1 of the spec.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

FEATURE_NAMES: tuple[str, ...] = (
    "sessions_started", "sessions_completed", "sessions_failed",
    "avg_session_duration_min", "avg_energy_delivered_kwh", "session_completion_rate",
    "avg_power_kw", "std_power_kw", "max_voltage_v", "min_voltage_v",
    "avg_current_a", "power_factor",
    "status_transitions", "time_in_faulted_pct", "time_in_available_pct",
    "time_in_unavailable_pct", "error_code_count", "unique_error_codes",
    "heartbeat_count", "heartbeat_gap_max_sec", "heartbeat_gap_std_sec",
    "ws_reconnections",
    "hour_of_day_sin", "day_of_week_sin",
)
assert len(FEATURE_NAMES) == 24


@dataclass
class FeatureVector:
    cp_id: str
    window_start: datetime
    window_end: datetime
    values: np.ndarray  # shape (24,)


def _decode(payload):
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (ValueError, TypeError):
            return {}
    return payload or {}


def extract(
    *,
    cp_id: str,
    window_start: datetime,
    window_end: datetime,
    events: Iterable[dict],
    sessions: Iterable[dict],
) -> FeatureVector:
    """Compute a 24-feature vector for one charger over one time window.

    Caller must pass:
      - events: dicts with keys (time, event_type, connector_id, payload)
      - sessions: dicts with keys (started_at, stopped_at, energy_kwh,
                                   duration_min, stop_reason)
    """
    events = list(events)
    sessions = list(sessions)
    window_sec = max(1.0, (window_end - window_start).total_seconds())

    # --- Sessions (indices 0-5) ---
    started = len(sessions)
    completed = sum(1 for s in sessions if s.get("stop_reason") == "EVDisconnected")
    failed = sum(
        1 for s in sessions
        if s.get("stop_reason") and s.get("stop_reason") != "EVDisconnected"
    )
    durations = [s.get("duration_min") for s in sessions if s.get("duration_min") is not None]
    energies = [s.get("energy_kwh") for s in sessions if s.get("energy_kwh") is not None]
    avg_dur = float(np.mean(durations)) if durations else 0.0
    avg_energy = float(np.mean(energies)) if energies else 0.0
    completion_rate = (completed / (completed + failed)) if (completed + failed) > 0 else 1.0

    # --- Power quality from MeterValues (indices 6-11) ---
    powers, voltages, currents = [], [], []
    for ev in events:
        if ev["event_type"] != "meter":
            continue
        p = _decode(ev["payload"])
        for mv in p.get("meter_value", []) or []:
            for sv in mv.get("sampled_value", []) or []:
                meas = sv.get("measurand") or "Energy.Active.Import.Register"
                try:
                    val = float(sv.get("value"))
                except (TypeError, ValueError):
                    continue
                if "Power.Active" in meas:
                    powers.append(val / 1000.0 if sv.get("unit") == "W" else val)
                elif meas == "Voltage":
                    voltages.append(val)
                elif "Current" in meas:
                    currents.append(val)
    avg_power = float(np.mean(powers)) if powers else 0.0
    std_power = float(np.std(powers)) if len(powers) > 1 else 0.0
    max_v = float(np.max(voltages)) if voltages else 0.0
    min_v = float(np.min(voltages)) if voltages else 0.0
    avg_i = float(np.mean(currents)) if currents else 0.0
    apparent = max_v * avg_i if (max_v and avg_i) else 0.0
    pf = (avg_power * 1000.0 / apparent) if apparent > 0 else 1.0

    # --- Status patterns (indices 12-17) ---
    status_events = [ev for ev in events if ev["event_type"] == "status"]
    transitions = len(status_events)
    durations_by_status: dict[str, float] = {}
    error_codes: list[str] = []
    last_t = window_start
    last_status = "Available"
    sorted_status = sorted(status_events, key=lambda e: e["time"])
    for ev in sorted_status:
        p = _decode(ev["payload"])
        durations_by_status[last_status] = (
            durations_by_status.get(last_status, 0.0)
            + (ev["time"] - last_t).total_seconds()
        )
        last_t = ev["time"]
        last_status = p.get("status", last_status)
        ec = p.get("error_code", "NoError")
        if ec and ec != "NoError":
            error_codes.append(ec)
    durations_by_status[last_status] = (
        durations_by_status.get(last_status, 0.0)
        + (window_end - last_t).total_seconds()
    )
    faulted_pct = durations_by_status.get("Faulted", 0.0) / window_sec
    available_pct = durations_by_status.get("Available", 0.0) / window_sec
    unavailable_pct = durations_by_status.get("Unavailable", 0.0) / window_sec
    error_count = len(error_codes)
    unique_errors = len(set(error_codes))

    # --- Connectivity (indices 18-21) ---
    hb_times = sorted(ev["time"] for ev in events if ev["event_type"] == "heartbeat")
    hb_count = len(hb_times)
    gaps = [
        (hb_times[i] - hb_times[i - 1]).total_seconds()
        for i in range(1, len(hb_times))
    ]
    hb_gap_max = max(gaps) if gaps else 0.0
    hb_gap_std = float(np.std(gaps)) if len(gaps) > 1 else 0.0
    ws_reconnects = sum(
        1 for ev in events
        if ev["event_type"] in ("disconnect", "boot")
    )

    # --- Temporal (indices 22-23) ---
    mid = window_start + (window_end - window_start) / 2
    hour_sin = math.sin(2 * math.pi * mid.hour / 24.0)
    day_sin = math.sin(2 * math.pi * mid.weekday() / 7.0)

    values = np.array([
        started, completed, failed, avg_dur, avg_energy, completion_rate,
        avg_power, std_power, max_v, min_v, avg_i, pf,
        transitions, faulted_pct, available_pct, unavailable_pct,
        error_count, unique_errors,
        hb_count, hb_gap_max, hb_gap_std, ws_reconnects,
        hour_sin, day_sin,
    ], dtype=np.float64)
    return FeatureVector(
        cp_id=cp_id, window_start=window_start, window_end=window_end, values=values,
    )


def to_dict(fv: FeatureVector) -> dict:
    return {name: float(val) for name, val in zip(FEATURE_NAMES, fv.values)}
