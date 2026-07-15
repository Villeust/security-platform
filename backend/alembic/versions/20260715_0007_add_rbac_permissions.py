"""add rbac permissions

Revision ID: 20260715_0007
Revises: 20260715_0006
Create Date: 2026-07-15 19:30:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0007"
down_revision: str | None = "20260715_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "admin.dashboard.view": "View admin dashboard",
    "admin.contractors.view": "View contractors",
    "admin.contractors.manage": "Manage contractors",
    "admin.users.view": "View users",
    "admin.users.manage": "Manage users",
    "admin.roles.view": "View roles",
    "admin.roles.manage": "Manage roles",
    "admin.audit.view": "View audit",
    "admin.system_status.view": "View system status",
    "requests.view": "View requests",
    "requests.create": "Create requests",
    "requests.update": "Update requests",
    "requests.publish": "Publish requests",
    "requests.change_status": "Change request status",
    "requests.close": "Close requests",
    "requests.comments.internal": "Use internal request comments",
    "requests.attachments.internal": "Use internal request attachments",
    "contractor.requests.view": "View contractor requests",
    "contractor.requests.accept": "Accept contractor assignments",
    "contractor.requests.update_status": "Update contractor assignment status",
    "contractor.comments.create": "Create contractor comments",
    "contractor.attachments.upload": "Upload contractor attachments",
    "reference_data.view": "View reference data",
    "reference_data.manage": "Manage reference data",
}


def split_code(code: str) -> tuple[str, str]:
    resource, _, action = code.rpartition(".")
    return resource, action


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=True)
    op.create_index(op.f("ix_permissions_resource"), "permissions", ["resource"], unique=False)
    op.create_index(op.f("ix_permissions_action"), "permissions", ["action"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": uuid4(),
                "code": code,
                "name": name,
                "description": None,
                "resource": split_code(code)[0],
                "action": split_code(code)[1],
                "is_system": True,
                "is_active": True,
            }
            for code, name in PERMISSIONS.items()
        ],
    )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_permissions_action"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_resource"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_code"), table_name="permissions")
    op.drop_table("permissions")
