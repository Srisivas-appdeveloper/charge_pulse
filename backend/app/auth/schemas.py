from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=50)


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
    organisation: OrgOut | None = None


class MeResponse(BaseModel):
    user: UserOut
    organisation: OrgOut | None


class AcceptInviteRequest(BaseModel):
    token: str
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=200)
