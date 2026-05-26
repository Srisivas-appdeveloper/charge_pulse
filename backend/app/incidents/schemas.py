from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IncidentOut(BaseModel):
    id: UUID
    cp_id: str
    severity: str
    failure_type: str | None
    anomaly_score: float | None
    title: str
    description: str | None
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_notes: str | None
    confirmed_failure_type: str | None
    auto_detected: bool


class IncidentListResponse(BaseModel):
    incidents: list[IncidentOut]
    total: int


class IncidentPatch(BaseModel):
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    confirmed_failure_type: str | None = None
