"""add request number

Revision ID: 20260715_0003
Revises: 20260715_0002
Create Date: 2026-07-15 00:03:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0003"
down_revision: str | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contractor_requests", sa.Column("request_number", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_contractor_requests_request_number"), "contractor_requests", ["request_number"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_contractor_requests_request_number"), table_name="contractor_requests")
    op.drop_column("contractor_requests", "request_number")
