from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    created_at: datetime


class OrgOut(BaseModel):
    id: UUID
    name: str
    email: str
    plan: str
    max_chargers: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    organisation: OrgOut


class MeResponse(BaseModel):
    user: UserOut
    organisation: OrgOut
