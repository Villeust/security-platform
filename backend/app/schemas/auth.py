from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.admin import ContractorMembershipResponse


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    provider: str = "LOCAL"


class ProviderStatus(BaseModel):
    provider: str
    configured: bool
    enabled: bool
    message: str | None = None


class AuthMeResponse(BaseModel):
    id: UUID
    username: str
    email: str | None
    display_name: str
    user_type: str
    auth_source: str
    is_active: bool
    is_locked: bool
    must_change_password: bool
    password_expires_at: datetime | None
    password_expired: bool
    password_days_remaining: int | None
    password_expiry_warning: bool
    role_ids: list[UUID]
    role_codes: list[str]
    permissions: list[str]
    contractor_memberships: list[ContractorMembershipResponse]


class LoginResponse(BaseModel):
    user: AuthMeResponse
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class MessageResponse(BaseModel):
    message: str
