"""add notification center foundation

Revision ID: 20260717_0012
Revises: 20260717_0011
Create Date: 2026-07-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0012"
down_revision: str | None = "20260717_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    body_format = sa.Enum("TEXT", "HTML", name="notification_body_format")
    severity = sa.Enum("INFO", "SUCCESS", "WARNING", "HIGH", "CRITICAL", name="notification_severity")
    event_status = sa.Enum("PENDING", "PROCESSING", "PROCESSED", "FAILED", name="notification_event_status")
    recipient_type = sa.Enum("INTERNAL", "CONTRACTOR", name="notification_recipient_type")
    channel = sa.Enum("IN_APP", "EMAIL", "TEAMS_FUTURE", "PUSH_FUTURE", name="notification_channel")
    delivery_status = sa.Enum("PENDING", "PROCESSING", "SENT", "DELIVERED", "FAILED", "CANCELLED", name="notification_delivery_status")
    digest_mode = sa.Enum("IMMEDIATE", "DAILY", "WEEKLY", "DISABLED", name="notification_digest_mode")

    bind = op.get_bind()
    for enum in (body_format, severity, event_status, recipient_type, channel, delivery_status, digest_mode):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("subject_template", sa.String(length=500), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("body_format", body_format, nullable=False),
        sa.Column("supported_channels", sa.JSON(), nullable=False),
        sa.Column("default_severity", severity, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_notification_template_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_notification_template_code_version"),
    )
    for col in ("code", "category", "is_active", "is_published"):
        op.create_index(f"ix_notification_templates_{col}", "notification_templates", [col])

    op.create_table(
        "notification_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("deduplication_key", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("tenant_type", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("safe_payload", sa.JSON(), nullable=False),
        sa.Column("payload_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", event_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_event_attempts_non_negative"),
        sa.CheckConstraint("payload_schema_version > 0", name="ck_notification_event_payload_schema_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deduplication_key", name="uq_notification_event_deduplication_key"),
    )
    for col in ("event_type", "source_type", "source_id", "deduplication_key", "correlation_id", "tenant_id", "occurred_at", "created_at", "status"):
        op.create_index(f"ix_notification_events_{col}", "notification_events", [col])

    op.create_table(
        "notification_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_event_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("message_deduplication_key", sa.String(length=255), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_type", recipient_type, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("action_url", sa.String(length=1000), nullable=True),
        sa.Column("action_label", sa.String(length=128), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("(recipient_type = 'INTERNAL' and tenant_id is null) or (recipient_type = 'CONTRACTOR' and tenant_id is not null)", name="ck_notification_message_recipient_tenant"),
        sa.ForeignKeyConstraint(["notification_event_id"], ["notification_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_deduplication_key", name="uq_notification_message_deduplication_key"),
    )
    for col in ("notification_event_id", "template_id", "message_deduplication_key", "recipient_user_id", "recipient_type", "tenant_id", "category", "severity", "is_read", "archived_at", "created_at"):
        op.create_index(f"ix_notification_messages_{col}", "notification_messages", [col])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_message_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_deduplication_key", sa.String(length=255), nullable=False),
        sa.Column("channel", channel, nullable=False),
        sa.Column("recipient_address", sa.String(length=320), nullable=True),
        sa.Column("status", delivery_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_safe", sa.String(length=1000), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_delivery_attempts_non_negative"),
        sa.ForeignKeyConstraint(["notification_message_id"], ["notification_messages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_deduplication_key", name="uq_notification_delivery_deduplication_key"),
    )
    for col in ("notification_message_id", "delivery_deduplication_key", "channel", "status", "next_attempt_at", "correlation_id", "created_at"):
        op.create_index(f"ix_notification_deliveries_{col}", "notification_deliveries", [col])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimum_severity", severity, nullable=False),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("digest_mode", digest_mode, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "category", name="uq_notification_preference_user_category"),
    )
    for col in ("user_id", "category"):
        op.create_index(f"ix_notification_preferences_{col}", "notification_preferences", [col])


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notification_deliveries")
    op.drop_table("notification_messages")
    op.drop_table("notification_events")
    op.drop_table("notification_templates")

    bind = op.get_bind()
    for enum_name in (
        "notification_digest_mode",
        "notification_delivery_status",
        "notification_channel",
        "notification_recipient_type",
        "notification_event_status",
        "notification_severity",
        "notification_body_format",
    ):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
