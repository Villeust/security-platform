"""add platform workflow engine

Revision ID: 20260716_0009
Revises: 20260715_0008
Create Date: 2026-07-16 22:00:00.000000
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0009"
down_revision: str | None = "20260715_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WORKFLOW_PERMISSIONS = {
    "workflows.view": "View workflow definitions",
    "workflows.manage": "Manage workflow definitions",
    "workflows.publish": "Publish workflow definitions",
    "workflows.instances.view": "View workflow instances",
    "workflows.instances.transition": "Execute workflow transitions",
    "workflows.sla.view": "View workflow SLA policies and timers",
    "workflows.sla.manage": "Manage workflow SLA policies",
}

ROLE_PERMISSION_CODES = {
    "PLATFORM_ADMIN": set(WORKFLOW_PERMISSIONS),
    "SECURITY_ADMIN": {
        "workflows.view",
        "workflows.manage",
        "workflows.publish",
        "workflows.instances.view",
        "workflows.sla.view",
        "workflows.sla.manage",
    },
    "SECURITY_OPERATOR": {
        "workflows.instances.view",
        "workflows.instances.transition",
    },
    "VIEWER": {
        "workflows.instances.view",
    },
}


def split_permission_code(code: str) -> tuple[str, str]:
    resource, _, action = code.rpartition(".")
    return resource, action


def as_uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def upgrade() -> None:
    state_type = sa.Enum("INITIAL", "ACTIVE", "WAITING", "COMPLETED", "CANCELLED", "CLOSED", name="workflow_state_type")
    actor_type = sa.Enum("SYSTEM", "INTERNAL_USER", "CONTRACTOR_USER", name="workflow_actor_type")
    sla_status = sa.Enum("ACTIVE", "PAUSED", "COMPLETED", "BREACHED", "CANCELLED", name="workflow_sla_status")
    event_status = sa.Enum("PENDING", "PROCESSING", "PROCESSED", "FAILED", name="domain_event_status")

    bind = op.get_bind()
    for enum in (state_type, actor_type, sla_status, event_status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_workflow_definition_code_version"),
    )
    op.create_index("ix_workflow_definitions_code", "workflow_definitions", ["code"])
    op.create_index("ix_workflow_definitions_entity_type", "workflow_definitions", ["entity_type"])

    op.create_table(
        "workflow_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state_type", state_type, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("color_token", sa.String(length=64), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_definition_id", "code", name="uq_workflow_state_definition_code"),
    )
    op.create_index("ix_workflow_states_workflow_definition_id", "workflow_states", ["workflow_definition_id"])

    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("from_state_id", sa.Uuid(), nullable=False),
        sa.Column("to_state_id", sa.Uuid(), nullable=False),
        sa.Column("permission_code", sa.String(length=128), nullable=True),
        sa.Column("requires_comment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_reason", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_attachment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_definition_id", "code", name="uq_workflow_transition_definition_code"),
    )
    op.create_index("ix_workflow_transitions_workflow_definition_id", "workflow_transitions", ["workflow_definition_id"])
    op.create_index("ix_workflow_transitions_from_state_id", "workflow_transitions", ["from_state_id"])
    op.create_index("ix_workflow_transitions_to_state_id", "workflow_transitions", ["to_state_id"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("instance_key", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("parent_instance_id", sa.Uuid(), nullable=True),
        sa.Column("current_state_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_instance_id"], ["workflow_instances.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_definition_id", "entity_type", "entity_id", "instance_key", name="uq_workflow_instance_definition_entity_key"),
    )
    op.create_index("ix_workflow_instances_workflow_definition_id", "workflow_instances", ["workflow_definition_id"])
    op.create_index("ix_workflow_instances_entity_type", "workflow_instances", ["entity_type"])
    op.create_index("ix_workflow_instances_entity_id", "workflow_instances", ["entity_id"])
    op.create_index("ix_workflow_instances_entity_lookup", "workflow_instances", ["entity_type", "entity_id", "instance_key"])
    op.create_index("ix_workflow_instances_current_state_id", "workflow_instances", ["current_state_id"])
    op.create_index("ix_workflow_instances_parent_instance_id", "workflow_instances", ["parent_instance_id"])

    op.create_table(
        "workflow_transition_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=False),
        sa.Column("transition_id", sa.Uuid(), nullable=False),
        sa.Column("from_state_id", sa.Uuid(), nullable=False),
        sa.Column("to_state_id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("safe_result_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transition_id"], ["workflow_transitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_state_id"], ["workflow_states.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("workflow_instance_id", "transition_id", "actor_id", "created_at", "correlation_id"):
        op.create_index(f"ix_workflow_transition_executions_{col}", "workflow_transition_executions", [col])

    op.create_table(
        "workflow_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=False),
        sa.Column("transition_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("safe_response_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transition_id"], ["workflow_transitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "workflow_instance_id", "transition_id", name="uq_workflow_idempotency_key"),
    )
    op.create_index("ix_workflow_idempotency_records_key", "workflow_idempotency_records", ["key"])
    op.create_index("ix_workflow_idempotency_records_workflow_instance_id", "workflow_idempotency_records", ["workflow_instance_id"])

    op.create_table(
        "workflow_sla_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        sa.Column("state_id", sa.Uuid(), nullable=True),
        sa.Column("transition_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("warning_before_minutes", sa.Integer(), nullable=True),
        sa.Column("business_calendar_code", sa.String(length=128), nullable=True),
        sa.Column("pause_in_state_codes", sa.JSON(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="WARNING"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["state_id"], ["workflow_states.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transition_id"], ["workflow_transitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_definition_id", "code", name="uq_workflow_sla_policy_definition_code"),
    )
    for col in ("workflow_definition_id", "state_id", "transition_id"):
        op.create_index(f"ix_workflow_sla_policies_{col}", "workflow_sla_policies", [col])

    op.create_table(
        "workflow_sla_timers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=False),
        sa.Column("sla_policy_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warning_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sla_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sla_policy_id"], ["workflow_sla_policies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_sla_timers_workflow_instance_id", "workflow_sla_timers", ["workflow_instance_id"])
    op.create_index("ix_workflow_sla_timers_sla_policy_id", "workflow_sla_timers", ["sla_policy_id"])
    op.create_index("ix_workflow_sla_timers_due_at", "workflow_sla_timers", ["due_at"])

    op.create_table(
        "domain_event_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("status", event_status, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("event_type", "aggregate_type", "aggregate_id", "created_at", "status"):
        op.create_index(f"ix_domain_event_outbox_{col}", "domain_event_outbox", [col])

    seed_workflow_permissions()


def seed_workflow_permissions() -> None:
    bind = op.get_bind()
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
    existing_codes = set(bind.execute(sa.text("select code from permissions")).scalars().all())
    new_permissions = []
    for code, name in WORKFLOW_PERMISSIONS.items():
        if code in existing_codes:
            continue
        resource, action = split_permission_code(code)
        new_permissions.append(
            {
                "id": uuid4(),
                "code": code,
                "name": name,
                "description": None,
                "resource": resource,
                "action": action,
                "is_system": True,
                "is_active": True,
            }
        )
    if new_permissions:
        op.bulk_insert(permissions_table, new_permissions)

    role_rows = bind.execute(sa.text("select id, code from roles")).mappings().all()
    permission_rows = bind.execute(sa.text("select id, code from permissions where code in :codes").bindparams(sa.bindparam("codes", expanding=True)), {"codes": tuple(WORKFLOW_PERMISSIONS)}).mappings().all()
    permission_id_by_code = {row["code"]: row["id"] for row in permission_rows}
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    role_permission_rows = []
    for role in role_rows:
        for permission_code in ROLE_PERMISSION_CODES.get(role["code"], set()):
            permission_id = permission_id_by_code.get(permission_code)
            if permission_id is not None:
                role_permission_rows.append({"role_id": as_uuid(role["id"]), "permission_id": as_uuid(permission_id)})
    if role_permission_rows:
        op.bulk_insert(role_permissions_table, role_permission_rows)


def downgrade() -> None:
    bind = op.get_bind()
    permission_rows = bind.execute(sa.text("select id from permissions where code in :codes").bindparams(sa.bindparam("codes", expanding=True)), {"codes": tuple(WORKFLOW_PERMISSIONS)}).scalars().all()
    if permission_rows:
        bind.execute(sa.text("delete from role_permissions where permission_id in :ids").bindparams(sa.bindparam("ids", expanding=True)), {"ids": tuple(permission_rows)})
        bind.execute(sa.text("delete from permissions where id in :ids").bindparams(sa.bindparam("ids", expanding=True)), {"ids": tuple(permission_rows)})

    op.drop_table("domain_event_outbox")
    op.drop_table("workflow_sla_timers")
    op.drop_table("workflow_sla_policies")
    op.drop_table("workflow_idempotency_records")
    op.drop_table("workflow_transition_executions")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_states")
    op.drop_table("workflow_definitions")

    for enum_name in ("domain_event_status", "workflow_sla_status", "workflow_actor_type", "workflow_state_type"):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
