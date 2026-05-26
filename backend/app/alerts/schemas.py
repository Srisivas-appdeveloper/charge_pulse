from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AlertConfigCreate(BaseModel):
    channel: str = Field(pattern="^(sms|whatsapp|email|webhook|slack)$")
    endpoint: str = Field(min_length=1, max_length=500)
    label: str | None = None
    severity_min: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


class AlertConfigUpdate(BaseModel):
    endpoint: str | None = None
    label: str | None = None
    severity_min: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    is_active: bool | None = None


class AlertConfigOut(BaseModel):
    id: UUID
    channel: str
    endpoint: str
    label: str | None
    severity_min: str
    is_active: bool
    created_at: datetime


class AlertConfigListResponse(BaseModel):
    configs: list[AlertConfigOut]
