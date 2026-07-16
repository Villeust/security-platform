from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.admin import AdminNotificationSeverity, AdminNotificationType, AuthSource, LockReason, UserType


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    is_active: bool
    users_count: int = 0
    permissions_count: int = 0
    created_at: datetime
    updated_at: datetime


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    resource: str
    action: str
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RolePermissionsUpdate(BaseModel):
    permission_ids: list[UUID] = Field(default_factory=list)


class ContractorMembershipPayload(BaseModel):
    contractor_id: UUID
    is_primary: bool = False
    is_active: bool = True


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    user_type: UserType
    auth_source: AuthSource = AuthSource.LOCAL
    role_ids: list[UUID] = Field(default_factory=list)
    contractor_memberships: list[ContractorMembershipPayload] = Field(default_factory=list)
    is_active: bool = True
    is_locked: bool = False
    temporary_password: str | None = Field(default=None, max_length=128)

    @field_validator("contractor_memberships")
    @classmethod
    def validate_unique_memberships(cls, value: list[ContractorMembershipPayload]) -> list[ContractorMembershipPayload]:
        ids = [item.contractor_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("contractor memberships must be unique")
        return value


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    user_type: UserType | None = None
    auth_source: AuthSource | None = None
    is_active: bool | None = None
    is_locked: bool | None = None


class UserRolesUpdate(BaseModel):
    role_ids: list[UUID] = Field(default_factory=list)


class UserContractorsUpdate(BaseModel):
    contractor_memberships: list[ContractorMembershipPayload] = Field(default_factory=list)


class ContractorMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    contractor_id: UUID
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    display_name: str
    user_type: UserType
    auth_source: AuthSource
    is_active: bool
    is_locked: bool
    last_login_at: datetime | None
    password_changed_at: datetime | None = None
    must_change_password: bool = False
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    last_login_ip: str | None = None
    external_subject: str | None = None
    external_directory_id: str | None = None
    authentication_enabled: bool = True
    password_expires_at: datetime | None = None
    password_expired_at: datetime | None = None
    password_expiry_notified_at: datetime | None = None
    lock_reason: LockReason | None = None
    locked_at: datetime | None = None
    locked_by_id: UUID | None = None
    unlock_reason: str | None = None
    role_ids: list[UUID] = []
    role_codes: list[str] = []
    permissions: list[str] = []
    contractor_memberships: list[ContractorMembershipResponse] = []
    created_at: datetime
    updated_at: datetime


class UserCreateResponse(UserResponse):
    temporary_password: str | None = None


class GenerateTemporaryPasswordResponse(BaseModel):
    user: UserResponse
    temporary_password: str


class UserLockRequest(BaseModel):
    reason: str = Field(default="ADMINISTRATIVE", max_length=128)
    comment: str | None = Field(default=None, max_length=500)
    revoke_sessions: bool = True


class UserUnlockRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class ContractorAdminCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    is_active: bool = True


class ContractorAdminUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class ContractorAdminResponse(BaseModel):
    id: UUID
    name: str
    code: str
    email: str | None
    phone: str | None
    is_active: bool
    users_count: int = 0
    responsibilities_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminDashboardResponse(BaseModel):
    contractors_total: int
    contractors_active: int
    users_total: int
    users_active: int
    cities_total: int
    facilities_total: int
    premises_total: int
    responsibilities_total: int
    requests_active: int
    work_types_total: int


class AdminSystemStatusItem(BaseModel):
    status: str
    description: str


class AdminSystemStatusResponse(BaseModel):
    backend: AdminSystemStatusItem
    database: AdminSystemStatusItem
    frontend_configured: AdminSystemStatusItem
    email_configured: AdminSystemStatusItem
    adfs_configured: AdminSystemStatusItem
    contractor_portal_status: AdminSystemStatusItem


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    actor_type: str
    action: str
    entity_type: str
    entity_id: UUID | None
    old_data: dict | None
    new_data: dict | None
    created_at: datetime
    ip_address: str | None
    user_agent: str | None
    correlation_id: str | None = None


class AdminNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: AdminNotificationType
    severity: AdminNotificationSeverity
    user_id: UUID | None
    title: str
    message: str
    details: dict | None
    created_at: datetime
    read_at: datetime | None
    read_by_id: UUID | None
    is_resolved: bool
    resolved_at: datetime | None
    resolved_by_id: UUID | None
