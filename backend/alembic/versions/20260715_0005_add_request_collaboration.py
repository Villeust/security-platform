"""add request collaboration

Revision ID: 20260715_0005
Revises: 20260715_0004
Create Date: 2026-07-15 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0005"
down_revision: str | None = "20260715_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

request_visibility = sa.Enum("SHARED", "INTERNAL", name="request_visibility")
request_attachment_category = sa.Enum("REQUEST_FILE", "WORK_RESULT", "ACT", "PHOTO", "DOCUMENT", "OTHER", name="request_attachment_category")
request_history_actor_type = sa.Enum("SYSTEM", "INTERNAL_USER", "CONTRACTOR_USER", name="request_history_actor_type")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("COMMENT_ADDED", "COMMENT_UPDATED", "COMMENT_DELETED", "ATTACHMENT_ADDED", "ATTACHMENT_DELETED", "WORK_RESULT_ADDED"):
            op.execute(f"ALTER TYPE request_history_event_type ADD VALUE IF NOT EXISTS '{value}'")

    request_visibility.create(bind, checkfirst=True)
    request_attachment_category.create(bind, checkfirst=True)

    op.create_table(
        "request_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("author_type", request_history_actor_type, nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("contractor_id", sa.Uuid(), nullable=True),
        sa.Column("visibility", request_visibility, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_id"], ["contractor_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_request_comments_request_id"), "request_comments", ["request_id"])
    op.create_index(op.f("ix_request_comments_contractor_id"), "request_comments", ["contractor_id"])

    op.create_table(
        "request_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by_type", request_history_actor_type, nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("contractor_id", sa.Uuid(), nullable=True),
        sa.Column("category", request_attachment_category, nullable=False),
        sa.Column("visibility", request_visibility, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["request_id"], ["contractor_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["request_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["comment_id"], ["request_comments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_request_attachments_request_id"), "request_attachments", ["request_id"])
    op.create_index(op.f("ix_request_attachments_assignment_id"), "request_attachments", ["assignment_id"])
    op.create_index(op.f("ix_request_attachments_comment_id"), "request_attachments", ["comment_id"])
    op.create_index(op.f("ix_request_attachments_contractor_id"), "request_attachments", ["contractor_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_request_attachments_contractor_id"), table_name="request_attachments")
    op.drop_index(op.f("ix_request_attachments_comment_id"), table_name="request_attachments")
    op.drop_index(op.f("ix_request_attachments_assignment_id"), table_name="request_attachments")
    op.drop_index(op.f("ix_request_attachments_request_id"), table_name="request_attachments")
    op.drop_table("request_attachments")
    op.drop_index(op.f("ix_request_comments_contractor_id"), table_name="request_comments")
    op.drop_index(op.f("ix_request_comments_request_id"), table_name="request_comments")
    op.drop_table("request_comments")
    request_attachment_category.drop(op.get_bind(), checkfirst=True)
    request_visibility.drop(op.get_bind(), checkfirst=True)
