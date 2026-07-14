"""add reference data

Revision ID: 20260714_0001
Revises:
Create Date: 2026-07-14 00:01:00.000000
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def create_reference_table(
    table_name: str,
    *columns: sa.Column,
    unique_name: bool = False,
) -> None:
    table_columns = [
        sa.Column("id", sa.Uuid(), nullable=False),
        *columns,
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    ]
    if unique_name:
        table_columns.append(sa.UniqueConstraint("name"))
    op.create_table(table_name, *table_columns)


def upgrade() -> None:
    create_reference_table(
        "cities",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("code"),
        unique_name=True,
    )
    op.create_index(op.f("ix_cities_name"), "cities", ["name"])
    op.create_index(op.f("ix_cities_code"), "cities", ["code"])

    create_reference_table(
        "facilities",
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_facilities_city_id"), "facilities", ["city_id"])
    op.create_index(op.f("ix_facilities_name"), "facilities", ["name"])
    op.create_index(op.f("ix_facilities_code"), "facilities", ["code"])

    create_reference_table(
        "premises",
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("owner_email", sa.String(length=255), nullable=True),
        sa.Column("owner_phone", sa.String(length=64), nullable=True),
        sa.Column("has_access_control", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_premises_facility_id"), "premises", ["facility_id"])
    op.create_index(op.f("ix_premises_name"), "premises", ["name"])

    create_reference_table(
        "contractors",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_contractors_name"), "contractors", ["name"])
    op.create_index(op.f("ix_contractors_code"), "contractors", ["code"])

    create_reference_table(
        "work_types",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("requires_premise", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_work_types_name"), "work_types", ["name"])
    op.create_index(op.f("ix_work_types_code"), "work_types", ["code"])

    create_reference_table(
        "contractor_responsibilities",
        sa.Column("contractor_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=True),
        sa.Column("facility_id", sa.Uuid(), nullable=True),
        sa.Column("work_type_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_type_id"], ["work_types.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "contractor_id",
            "city_id",
            "facility_id",
            "work_type_id",
            name="uq_contractor_responsibility_scope",
        ),
    )
    op.create_index(op.f("ix_contractor_responsibilities_contractor_id"), "contractor_responsibilities", ["contractor_id"])
    op.create_index(op.f("ix_contractor_responsibilities_city_id"), "contractor_responsibilities", ["city_id"])
    op.create_index(op.f("ix_contractor_responsibilities_facility_id"), "contractor_responsibilities", ["facility_id"])
    op.create_index(op.f("ix_contractor_responsibilities_work_type_id"), "contractor_responsibilities", ["work_type_id"])

    work_types = sa.table(
        "work_types",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String),
        sa.column("code", sa.String),
        sa.column("requires_premise", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        work_types,
        [
            {
                "id": UUID("00000000-0000-0000-0000-000000000101"),
                "name": "СКУД",
                "code": "ACCESS_CONTROL",
                "requires_premise": True,
                "is_active": True,
            },
            {
                "id": UUID("00000000-0000-0000-0000-000000000102"),
                "name": "СВН",
                "code": "CCTV",
                "requires_premise": False,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("contractor_responsibilities")
    op.drop_table("work_types")
    op.drop_table("contractors")
    op.drop_table("premises")
    op.drop_table("facilities")
    op.drop_table("cities")
