"""add auth and connections

Revision ID: 20260715_0008
Revises: 20260715_0007
Create Date: 2026-07-15 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0008"
down_revision: str | None = "20260715_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    lock_reason = sa.Enum("TOO_MANY_FAILED_ATTEMPTS", "ADMINISTRATIVE", "SECURITY_POLICY", "PASSWORD_EXPIRED_RESTRICTED", "OTHER", name="lock_reason")
    notification_type = sa.Enum("USER_ACCOUNT_LOCKED", "USER_ACCOUNT_UNLOCKED", "PASSWORD_EXPIRING", "PASSWORD_EXPIRED", "REPEATED_LOGIN_FAILURES", "SUSPICIOUS_LOGIN_ACTIVITY", name="admin_notification_type")
    notification_severity = sa.Enum("INFO", "WARNING", "HIGH", "CRITICAL", name="admin_notification_severity")
    provider_type = sa.Enum("LDAP", "ADFS", "SMTP", name="connection_provider_type")
    event_status = sa.Enum("INFO", "SUCCESS", "FAILED", name="connection_event_status")

    bind = op.get_bind()
    for enum in (lock_reason, notification_type, notification_severity, provider_type, event_status):
        enum.create(bind, checkfirst=True)

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_login_ip", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("external_subject", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("external_directory_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("authentication_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("password_expired_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("password_expiry_notified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("lock_reason", lock_reason, nullable=True))
        batch.add_column(sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("locked_by_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("unlock_reason", sa.String(length=500), nullable=True))
        batch.create_foreign_key("fk_users_locked_by_id_users", "users", ["locked_by_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_users_external_subject", ["external_subject"])
        batch.create_index("ix_users_external_directory_id", ["external_directory_id"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access_token_hash", sa.String(length=128), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=128), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_access_token_hash", "auth_sessions", ["access_token_hash"], unique=True)
    op.create_index("ix_auth_sessions_refresh_token_hash", "auth_sessions", ["refresh_token_hash"], unique=True)
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])

    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("severity", notification_severity, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_by_id", sa.Uuid(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["read_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("type", "severity", "user_id", "created_at", "is_resolved"):
        op.create_index(f"ix_admin_notifications_{col}", "admin_notifications", [col])

    op.create_table(
        "connection_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("encrypted_secrets", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=64), nullable=True),
        sa.Column("last_test_message", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_type", name="uq_connection_provider_type"),
    )
    op.create_index("ix_connection_configurations_provider_type", "connection_configurations", ["provider_type"])

    op.create_table(
        "directory_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("distinguished_name", sa.String(length=1000), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_configuration_id", sa.Uuid(), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["source_configuration_id"], ["connection_configurations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_type", "external_id", name="uq_directory_group_external"),
    )
    op.create_index("ix_directory_groups_provider_type", "directory_groups", ["provider_type"])
    op.create_index("ix_directory_groups_name", "directory_groups", ["name"])

    op.create_table(
        "auth_group_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directory_group_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("contractor_id", sa.Uuid(), nullable=True),
        sa.Column("all_cities", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["directory_group_id"], ["directory_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("directory_group_id", "role_id", "contractor_id"):
        op.create_index(f"ix_auth_group_mappings_{col}", "auth_group_mappings", [col])

    op.create_table(
        "auth_group_mapping_cities",
        sa.Column("mapping_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["mapping_id"], ["auth_group_mappings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("mapping_id", "city_id"),
        sa.UniqueConstraint("mapping_id", "city_id", name="uq_auth_group_mapping_city"),
    )

    op.create_table(
        "connection_event_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("configuration_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("status", event_status, nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("safe_details", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["connection_configurations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("provider_type", "configuration_id", "event_type", "status", "created_at"):
        op.create_index(f"ix_connection_event_logs_{col}", "connection_event_logs", [col])


def downgrade() -> None:
    op.drop_table("connection_event_logs")
    op.drop_table("auth_group_mapping_cities")
    op.drop_table("auth_group_mappings")
    op.drop_table("directory_groups")
    op.drop_table("connection_configurations")
    op.drop_table("admin_notifications")
    op.drop_table("auth_sessions")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_locked_by_id_users", type_="foreignkey")
        batch.drop_index("ix_users_external_directory_id")
        batch.drop_index("ix_users_external_subject")
        for col in (
            "unlock_reason",
            "locked_by_id",
            "locked_at",
            "lock_reason",
            "password_expiry_notified_at",
            "password_expired_at",
            "password_expires_at",
            "authentication_enabled",
            "external_directory_id",
            "external_subject",
            "last_login_ip",
            "locked_until",
            "failed_login_attempts",
            "must_change_password",
            "password_changed_at",
            "password_hash",
        ):
            batch.drop_column(col)
