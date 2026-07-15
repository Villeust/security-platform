"""add contractor requests

Revision ID: 20260715_0002
Revises: 20260714_0001
Create Date: 2026-07-15 00:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260714_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


request_status = sa.Enum("NEW", "ASSIGNED", name="request_status")
assignment_status = sa.Enum("ASSIGNED", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="assignment_status")


def upgrade() -> None:
    request_status.create(op.get_bind(), checkfirst=True)
    assignment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "contractor_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("premise_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("status", request_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["premise_id"], ["premises.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contractor_requests_city_id"), "contractor_requests", ["city_id"])
    op.create_index(op.f("ix_contractor_requests_facility_id"), "contractor_requests", ["facility_id"])
    op.create_index(op.f("ix_contractor_requests_premise_id"), "contractor_requests", ["premise_id"])

    op.create_table(
        "request_work_types",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("work_type_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["contractor_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_type_id"], ["work_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("request_id", "work_type_id"),
        sa.UniqueConstraint("request_id", "work_type_id", name="uq_request_work_type"),
    )

    op.create_table(
        "request_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("contractor_id", sa.Uuid(), nullable=False),
        sa.Column("work_type_id", sa.Uuid(), nullable=False),
        sa.Column("status", assignment_status, nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_id"], ["contractor_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_type_id"], ["work_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "work_type_id", name="uq_request_assignment_work_type"),
    )
    op.create_index(op.f("ix_request_assignments_request_id"), "request_assignments", ["request_id"])
    op.create_index(op.f("ix_request_assignments_contractor_id"), "request_assignments", ["contractor_id"])
    op.create_index(op.f("ix_request_assignments_work_type_id"), "request_assignments", ["work_type_id"])

    op.create_table(
        "contractor_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("contractor_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "contractor_id", name="uq_contractor_user"),
    )
    op.create_index(op.f("ix_contractor_users_user_id"), "contractor_users", ["user_id"])
    op.create_index(op.f("ix_contractor_users_contractor_id"), "contractor_users", ["contractor_id"])


def downgrade() -> None:
    op.drop_table("contractor_users")
    op.drop_table("request_assignments")
    op.drop_table("request_work_types")
    op.drop_table("contractor_requests")
    assignment_status.drop(op.get_bind(), checkfirst=True)
    request_status.drop(op.get_bind(), checkfirst=True)
