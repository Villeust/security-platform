"""add request workflow

Revision ID: 20260715_0004
Revises: 20260715_0003
Create Date: 2026-07-15 00:04:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0004"
down_revision: str | None = "20260715_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


history_event_type = sa.Enum(
    "CREATED",
    "UPDATED",
    "PUBLISHED",
    "STATUS_CHANGED",
    "ASSIGNMENT_CREATED",
    "ASSIGNMENT_ACCEPTED",
    "ASSIGNMENT_STATUS_CHANGED",
    "REOPENED",
    "CLOSED",
    "CANCELLED",
    name="request_history_event_type",
)
history_actor_type = sa.Enum("SYSTEM", "INTERNAL_USER", "CONTRACTOR_USER", name="request_history_actor_type")
request_status = sa.Enum(
    "DRAFT",
    "NEW",
    "PARTIALLY_ASSIGNED",
    "ASSIGNED",
    "IN_PROGRESS",
    "COMPLETED",
    "CLOSED",
    "CANCELLED",
    name="request_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("DRAFT", "PARTIALLY_ASSIGNED", "IN_PROGRESS", "COMPLETED", "CLOSED", "CANCELLED"):
            op.execute(f"ALTER TYPE request_status ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column("contractor_requests", sa.Column("priority", sa.String(length=32), nullable=True))
    op.add_column("contractor_requests", sa.Column("desired_completion_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contractor_requests", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contractor_requests", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("contractor_requests") as batch_op:
        batch_op.alter_column("city_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.alter_column("facility_id", existing_type=sa.Uuid(), nullable=True)

    history_event_type.create(bind, checkfirst=True)
    history_actor_type.create(bind, checkfirst=True)
    op.create_table(
        "request_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", history_event_type, nullable=False),
        sa.Column("old_status", request_status, nullable=True),
        sa.Column("new_status", request_status, nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_type", history_actor_type, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["contractor_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_request_history_request_id"), "request_history", ["request_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_request_history_request_id"), table_name="request_history")
    op.drop_table("request_history")
    history_actor_type.drop(op.get_bind(), checkfirst=True)
    history_event_type.drop(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("contractor_requests") as batch_op:
        batch_op.alter_column("facility_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.alter_column("city_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_column("contractor_requests", "closed_at")
    op.drop_column("contractor_requests", "completed_at")
    op.drop_column("contractor_requests", "desired_completion_date")
    op.drop_column("contractor_requests", "priority")
