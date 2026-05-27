"""FastAPI user management schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(admin|member|viewer)$")


class UserUpdateRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|member|viewer)$")


class UserOut(BaseModel):
    id: UUID
    org_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    invited_by: UUID | None = None
    invite_accepted_at: datetime | None = None
