"""Auth bounded-context DTOs.

Extracted from routers/auth.py so OpenAPI, tests, and any future clients
share one contract definition.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    # Absent for legacy clients; present after login/refresh (see /auth/refresh).
    refresh_token: str | None = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutResponse(BaseModel):
    detail: str
    revoked: bool


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    is_active: bool | None = None
    roles: list[str] | None = None  # Role names to assign
