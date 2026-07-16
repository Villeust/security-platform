from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.reference_data import Contractor, TimestampMixin, utc_now


class UserType(StrEnum):
    INTERNAL = "INTERNAL"
    CONTRACTOR = "CONTRACTOR"


class AuthSource(StrEnum):
    LOCAL = "LOCAL"
    ADFS = "ADFS"
    LDAP = "LDAP"


class LockReason(StrEnum):
    TOO_MANY_FAILED_ATTEMPTS = "TOO_MANY_FAILED_ATTEMPTS"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    SECURITY_POLICY = "SECURITY_POLICY"
    PASSWORD_EXPIRED_RESTRICTED = "PASSWORD_EXPIRED_RESTRICTED"
    OTHER = "OTHER"


class AdminNotificationType(StrEnum):
    USER_ACCOUNT_LOCKED = "USER_ACCOUNT_LOCKED"
    USER_ACCOUNT_UNLOCKED = "USER_ACCOUNT_UNLOCKED"
    PASSWORD_EXPIRING = "PASSWORD_EXPIRING"
    PASSWORD_EXPIRED = "PASSWORD_EXPIRED"
    REPEATED_LOGIN_FAILURES = "REPEATED_LOGIN_FAILURES"
    SUSPICIOUS_LOGIN_ACTIVITY = "SUSPICIOUS_LOGIN_ACTIVITY"


class AdminNotificationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConnectionProviderType(StrEnum):
    LDAP = "LDAP"
    ADFS = "ADFS"
    SMTP = "SMTP"


class ConnectionTestStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ConnectionEventStatus(StrEnum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_type: Mapped[UserType] = mapped_column(Enum(UserType, name="user_type"), nullable=False)
    auth_source: Mapped[AuthSource] = mapped_column(Enum(AuthSource, name="auth_source"), nullable=False, default=AuthSource.LOCAL)
    password_hash: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    external_directory_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    authentication_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_expiry_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_reason: Mapped[LockReason | None] = mapped_column(Enum(LockReason, name="lock_reason"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    unlock_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    contractor_memberships: Mapped[list["ContractorMembership"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="AuthSession.user_id")


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users: Mapped[list["UserRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(back_populates="users")


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    roles: Mapped[list["RolePermission"]] = relationship(back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True)

    role: Mapped[Role] = relationship(back_populates="permissions")
    permission: Mapped[Permission] = relationship(back_populates="roles")


class ContractorMembership(TimestampMixin, Base):
    __tablename__ = "contractor_memberships"
    __table_args__ = (UniqueConstraint("user_id", "contractor_id", name="uq_contractor_membership"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contractor_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.id", ondelete="RESTRICT"), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship(back_populates="contractor_memberships")
    contractor: Mapped[Contractor] = relationship()


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM_ADMIN_STUB")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    old_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="sessions", foreign_keys=[user_id])


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[AdminNotificationType] = mapped_column(Enum(AdminNotificationType, name="admin_notification_type"), nullable=False, index=True)
    severity: Mapped[AdminNotificationSeverity] = mapped_column(Enum(AdminNotificationSeverity, name="admin_notification_severity"), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ConnectionConfiguration(TimestampMixin, Base):
    __tablename__ = "connection_configurations"
    __table_args__ = (UniqueConstraint("provider_type", name="uq_connection_provider_type"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_type: Mapped[ConnectionProviderType] = mapped_column(Enum(ConnectionProviderType, name="connection_provider_type"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    configuration_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    encrypted_secrets: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DirectoryGroup(Base):
    __tablename__ = "directory_groups"
    __table_args__ = (UniqueConstraint("provider_type", "external_id", name="uq_directory_group_external"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_type: Mapped[ConnectionProviderType] = mapped_column(Enum(ConnectionProviderType, name="connection_provider_type"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    distinguished_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_configuration_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("connection_configurations.id", ondelete="SET NULL"), nullable=True)
    member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuthGroupMapping(TimestampMixin, Base):
    __tablename__ = "auth_group_mappings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    directory_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("directory_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True)
    contractor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.id", ondelete="RESTRICT"), nullable=True, index=True)
    all_cities: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuthGroupMappingCity(Base):
    __tablename__ = "auth_group_mapping_cities"
    __table_args__ = (UniqueConstraint("mapping_id", "city_id", name="uq_auth_group_mapping_city"),)

    mapping_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("auth_group_mappings.id", ondelete="CASCADE"), primary_key=True)
    city_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True)


class ConnectionEventLog(Base):
    __tablename__ = "connection_event_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_type: Mapped[ConnectionProviderType] = mapped_column(Enum(ConnectionProviderType, name="connection_provider_type"), nullable=False, index=True)
    configuration_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("connection_configurations.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[ConnectionEventStatus] = mapped_column(Enum(ConnectionEventStatus, name="connection_event_status"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
