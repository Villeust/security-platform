from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.reference_data import TimestampMixin, utc_now


class NotificationBodyFormat(StrEnum):
    TEXT = "TEXT"
    HTML = "HTML"


class NotificationSeverity(StrEnum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotificationEventStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class NotificationRecipientType(StrEnum):
    INTERNAL = "INTERNAL"
    CONTRACTOR = "CONTRACTOR"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    TEAMS_FUTURE = "TEAMS_FUTURE"
    PUSH_FUTURE = "PUSH_FUTURE"


class NotificationDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationDigestMode(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    DISABLED = "DISABLED"


class NotificationTemplate(TimestampMixin, Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_notification_template_code_version"),
        CheckConstraint("version > 0", name="ck_notification_template_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subject_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_format: Mapped[NotificationBodyFormat] = mapped_column(Enum(NotificationBodyFormat, name="notification_body_format"), nullable=False)
    supported_channels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    default_severity: Mapped[NotificationSeverity] = mapped_column(Enum(NotificationSeverity, name="notification_severity"), nullable=False, default=NotificationSeverity.INFO)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_notification_event_deduplication_key"),
        CheckConstraint("attempts >= 0", name="ck_notification_event_attempts_non_negative"),
        CheckConstraint("payload_schema_version > 0", name="ck_notification_event_payload_schema_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    deduplication_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tenant_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    safe_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    status: Mapped[NotificationEventStatus] = mapped_column(Enum(NotificationEventStatus, name="notification_event_status"), nullable=False, default=NotificationEventStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    messages: Mapped[list["NotificationMessage"]] = relationship(back_populates="event")


class NotificationMessage(TimestampMixin, Base):
    __tablename__ = "notification_messages"
    __table_args__ = (
        UniqueConstraint("message_deduplication_key", name="uq_notification_message_deduplication_key"),
        CheckConstraint(
            "(recipient_type = 'INTERNAL' and tenant_id is null) or (recipient_type = 'CONTRACTOR' and tenant_id is not null)",
            name="ck_notification_message_recipient_tenant",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    notification_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("notification_events.id", ondelete="RESTRICT"), nullable=False, index=True)
    template_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("notification_templates.id", ondelete="RESTRICT"), nullable=True, index=True)
    message_deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient_type: Mapped[NotificationRecipientType] = mapped_column(Enum(NotificationRecipientType, name="notification_recipient_type"), nullable=False, index=True)
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[NotificationSeverity] = mapped_column(Enum(NotificationSeverity, name="notification_severity"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    action_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[NotificationEvent] = relationship(back_populates="messages")
    template: Mapped[NotificationTemplate | None] = relationship()
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(back_populates="message")


class NotificationDelivery(TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("delivery_deduplication_key", name="uq_notification_delivery_deduplication_key"),
        CheckConstraint("attempts >= 0", name="ck_notification_delivery_attempts_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    notification_message_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("notification_messages.id", ondelete="RESTRICT"), nullable=False, index=True)
    delivery_deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel, name="notification_channel"), nullable=False, index=True)
    recipient_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[NotificationDeliveryStatus] = mapped_column(Enum(NotificationDeliveryStatus, name="notification_delivery_status"), nullable=False, default=NotificationDeliveryStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_safe: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    message: Mapped[NotificationMessage] = relationship(back_populates="deliveries")


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_notification_preference_user_category"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_severity: Mapped[NotificationSeverity] = mapped_column(Enum(NotificationSeverity, name="notification_severity"), nullable=False, default=NotificationSeverity.INFO)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    digest_mode: Mapped[NotificationDigestMode] = mapped_column(Enum(NotificationDigestMode, name="notification_digest_mode"), nullable=False, default=NotificationDigestMode.IMMEDIATE)
