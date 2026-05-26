from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChargerCreate(BaseModel):
    cp_id: str = Field(min_length=1, max_length=100)
    display_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    lat: float | None = None
    lng: float | None = None
    connector_count: int = 1


class ChargerOut(BaseModel):
    cp_id: str
    display_name: str | None
    vendor: str | None
    model: str | None
    firmware_version: str | None
    serial_number: str | None
    connector_count: int
    status: str
    health_score: float
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    lat: float | None
    lng: float | None
    last_boot_at: datetime | None
    last_heartbeat_at: datetime | None
    last_session_at: datetime | None
    created_at: datetime


class ChargerListResponse(BaseModel):
    chargers: list[ChargerOut]
    total: int
    page: int
    pages: int


class ChargerDetailResponse(BaseModel):
    charger: ChargerOut
    recent_incidents: list[dict[str, Any]]
    current_anomaly_score: float | None


class TelemetryEvent(BaseModel):
    time: datetime
    event_type: str
    connector_id: int | None
    payload: dict[str, Any]


class TelemetryResponse(BaseModel):
    events: list[TelemetryEvent]


class HealthPoint(BaseModel):
    time: datetime
    health_score: float | None
    anomaly_score: float | None


class HealthResponse(BaseModel):
    timeline: list[HealthPoint]


class SessionOut(BaseModel):
    id: int
    connector_id: int
    id_tag: str | None
    meter_start: int | None
    meter_stop: int | None
    energy_kwh: float | None
    duration_min: float | None
    stop_reason: str | None
    started_at: datetime
    stopped_at: datetime | None


class SessionListResponse(BaseModel):
    sessions: list[SessionOut]
    total: int


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    status: str
    request_id: str
    response: dict[str, Any] | None = None
    error: str | None = None


class BulkImportRow(BaseModel):
    cp_id: str
    display_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    lat: float | None = None
    lng: float | None = None
    connector_count: int = 1


class BulkImportRequest(BaseModel):
    chargers: list[BulkImportRow]


class BulkImportResponse(BaseModel):
    created: int
    skipped: list[dict[str, str]]
