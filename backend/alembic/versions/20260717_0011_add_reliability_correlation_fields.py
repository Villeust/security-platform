"""add reliability correlation fields

Revision ID: 20260717_0011
Revises: 20260716_0010
Create Date: 2026-07-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_0011"
down_revision = "20260716_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_audit_logs") as batch:
        batch.add_column(sa.Column("correlation_id", sa.String(length=128), nullable=True))
        batch.create_index("ix_admin_audit_logs_correlation_id", ["correlation_id"])

    with op.batch_alter_table("domain_event_outbox") as batch:
        batch.add_column(sa.Column("correlation_id", sa.String(length=128), nullable=True))
        batch.create_index("ix_domain_event_outbox_correlation_id", ["correlation_id"])


def downgrade() -> None:
    with op.batch_alter_table("domain_event_outbox") as batch:
        batch.drop_index("ix_domain_event_outbox_correlation_id")
        batch.drop_column("correlation_id")

    with op.batch_alter_table("admin_audit_logs") as batch:
        batch.drop_index("ix_admin_audit_logs_correlation_id")
        batch.drop_column("correlation_id")
