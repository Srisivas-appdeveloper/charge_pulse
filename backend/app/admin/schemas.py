"""Superadmin schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    plan: str = Field(default="starter", pattern="^(starter|pro|enterprise)$")


class OrgAdminOut(BaseModel):
    id: UUID
    name: str
    email: str
    plan: str
    max_chargers: int
    is_active: bool
    created_at: datetime
    charger_count: int


class OrgDetailAdminOut(BaseModel):
    id: UUID
    name: str
    email: str
    plan: str
    max_chargers: int
    is_active: bool
    created_at: datetime
    charger_count: int
    open_incidents_count: int
    total_sessions_count: int


class AdminDashboardStats(BaseModel):
    total_orgs: int
    total_chargers: int
    total_incidents: int
    mrr: float
