"""seed contractor request workflow

Revision ID: 20260716_0010
Revises: 20260716_0009
Create Date: 2026-07-16 23:00:00.000000
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0010"
down_revision: str | None = "20260716_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKFLOW_CODE = "CONTRACTOR_REQUEST"
ENTITY_TYPE = "CONTRACTOR_REQUEST"
INSTANCE_KEY = "default"

STATES = [
    ("DRAFT", "INITIAL", True, False, 10),
    ("NEW", "ACTIVE", False, False, 20),
    ("PARTIALLY_ASSIGNED", "ACTIVE", False, False, 30),
    ("ASSIGNED", "ACTIVE", False, False, 40),
    ("IN_PROGRESS", "ACTIVE", False, False, 50),
    ("COMPLETED", "COMPLETED", False, False, 60),
    ("CLOSED", "CLOSED", False, True, 70),
    ("CANCELLED", "CANCELLED", False, True, 80),
]

TRANSITIONS = [
    ("PUBLISH_TO_NEW", "Publish without assignment", "DRAFT", "NEW", "requests.publish", 10),
    ("PUBLISH_TO_PARTIALLY_ASSIGNED", "Publish partially assigned", "DRAFT", "PARTIALLY_ASSIGNED", "requests.publish", 20),
    ("PUBLISH_TO_ASSIGNED", "Publish assigned", "DRAFT", "ASSIGNED", "requests.publish", 30),
    ("ASSIGN_PARTIALLY", "Assign partially", "NEW", "PARTIALLY_ASSIGNED", "requests.update", 40),
    ("ASSIGN", "Assign", "NEW", "ASSIGNED", "requests.update", 50),
    ("CANCEL_FROM_NEW", "Cancel", "NEW", "CANCELLED", "requests.change_status", 60),
    ("ASSIGN_REMAINING", "Assign remaining", "PARTIALLY_ASSIGNED", "ASSIGNED", "requests.update", 70),
    ("START_WORK_FROM_PARTIALLY_ASSIGNED", "Start work from partial assignment", "PARTIALLY_ASSIGNED", "IN_PROGRESS", None, 80),
    ("CANCEL_FROM_PARTIALLY_ASSIGNED", "Cancel", "PARTIALLY_ASSIGNED", "CANCELLED", None, 90),
    ("START_WORK", "Start work", "ASSIGNED", "IN_PROGRESS", None, 100),
    ("CANCEL_FROM_ASSIGNED", "Cancel", "ASSIGNED", "CANCELLED", None, 110),
    ("COMPLETE", "Complete", "IN_PROGRESS", "COMPLETED", None, 120),
    ("CANCEL_FROM_IN_PROGRESS", "Cancel", "IN_PROGRESS", "CANCELLED", None, 130),
    ("CLOSE", "Close", "COMPLETED", "CLOSED", "requests.close", 140),
    ("REOPEN", "Reopen", "COMPLETED", "IN_PROGRESS", "requests.change_status", 150),
]

ALLOWED_PERMISSIONS = {
    "START_WORK_FROM_PARTIALLY_ASSIGNED": '["requests.change_status","contractor.requests.update_status","contractor.requests.accept"]',
    "START_WORK": '["requests.change_status","contractor.requests.update_status","contractor.requests.accept"]',
    "COMPLETE": '["requests.change_status","contractor.requests.update_status"]',
    "CANCEL_FROM_NEW": '["requests.change_status","contractor.requests.update_status"]',
    "CANCEL_FROM_PARTIALLY_ASSIGNED": '["requests.change_status","contractor.requests.update_status"]',
    "CANCEL_FROM_ASSIGNED": '["requests.change_status","contractor.requests.update_status"]',
    "CANCEL_FROM_IN_PROGRESS": '["requests.change_status","contractor.requests.update_status"]',
}


def as_uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def db_uuid(value, bind):
    item = as_uuid(value)
    return item.hex if bind.dialect.name == "sqlite" else str(item)


def upgrade() -> None:
    bind = op.get_bind()
    definition = bind.execute(
        sa.text("select id from workflow_definitions where code = :code and version = 1"),
        {"code": WORKFLOW_CODE},
    ).mappings().first()
    if definition is None:
        definition_id = uuid4()
        bind.execute(
            sa.text(
                """
                insert into workflow_definitions
                    (id, code, name, description, entity_type, version, is_active, is_published, created_at, updated_at, published_at)
                values
                    (:id, :code, :name, null, :entity_type, 1, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, null)
                """
            ),
        {"id": db_uuid(definition_id, bind), "code": WORKFLOW_CODE, "name": "Contractor Request", "entity_type": ENTITY_TYPE},
        )
    else:
        definition_id = as_uuid(definition["id"])

    state_ids: dict[str, UUID] = {}
    for code, state_type, is_initial, is_terminal, sort_order in STATES:
        state = bind.execute(
            sa.text("select id from workflow_states where workflow_definition_id = :definition_id and code = :code"),
            {"definition_id": db_uuid(definition_id, bind), "code": code},
        ).mappings().first()
        if state is None:
            state_id = uuid4()
            bind.execute(
                sa.text(
                    """
                    insert into workflow_states
                        (id, workflow_definition_id, code, name, description, state_type, sort_order, is_initial, is_terminal, color_token, icon, is_active)
                    values
                        (:id, :definition_id, :code, :name, null, :state_type, :sort_order, :is_initial, :is_terminal, null, null, 1)
                    """
                ),
                {
                    "id": db_uuid(state_id, bind),
                    "definition_id": db_uuid(definition_id, bind),
                    "code": code,
                    "name": code,
                    "state_type": state_type,
                    "sort_order": sort_order,
                    "is_initial": is_initial,
                    "is_terminal": is_terminal,
                },
            )
        else:
            state_id = as_uuid(state["id"])
        state_ids[code] = state_id

    for code, name, from_state, to_state, permission_code, sort_order in TRANSITIONS:
        exists = bind.execute(
            sa.text("select id from workflow_transitions where workflow_definition_id = :definition_id and code = :code"),
            {"definition_id": db_uuid(definition_id, bind), "code": code},
        ).first()
        if exists is not None:
            continue
        bind.execute(
            sa.text(
                """
                insert into workflow_transitions
                    (id, workflow_definition_id, code, name, description, from_state_id, to_state_id, permission_code,
                     requires_comment, requires_reason, requires_attachment, confirmation_required, sort_order, is_active, configuration_json)
                values
                    (:id, :definition_id, :code, :name, null, :from_state_id, :to_state_id, :permission_code,
                     0, 0, 0, 0, :sort_order, 1, :configuration_json)
                """
            ),
            {
                "id": db_uuid(uuid4(), bind),
                "definition_id": db_uuid(definition_id, bind),
                "code": code,
                "name": name,
                "from_state_id": db_uuid(state_ids[from_state], bind),
                "to_state_id": db_uuid(state_ids[to_state], bind),
                "permission_code": permission_code,
                "sort_order": sort_order,
                "configuration_json": '{"allowed_actor_types":["INTERNAL_USER","CONTRACTOR_USER"],"allowed_permissions":' + ALLOWED_PERMISSIONS.get(code, "[]") + "}",
            },
        )

    bind.execute(
        sa.text(
            """
            update workflow_definitions
            set is_active = 1, is_published = 1, published_at = coalesce(published_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP
            where id = :definition_id
            """
        ),
        {"definition_id": db_uuid(definition_id, bind)},
    )

    requests = bind.execute(
        sa.text("select id, status, created_at, updated_at, completed_at from contractor_requests")
    ).mappings().all()
    for request in requests:
        request_id = as_uuid(request["id"])
        existing = bind.execute(
            sa.text(
                """
                select wi.id
                from workflow_instances wi
                where wi.workflow_definition_id = :definition_id
                  and wi.entity_type = :entity_type
                  and wi.entity_id = :entity_id
                  and wi.instance_key = :instance_key
                """
            ),
            {
                "definition_id": db_uuid(definition_id, bind),
                "entity_type": ENTITY_TYPE,
                "entity_id": db_uuid(request_id, bind),
                "instance_key": INSTANCE_KEY,
            },
        ).first()
        if existing is not None:
            continue
        status_code = request["status"]
        bind.execute(
            sa.text(
                """
                insert into workflow_instances
                    (id, workflow_definition_id, workflow_version, entity_type, entity_id, instance_key, parent_instance_id,
                     current_state_id, started_at, completed_at, cancelled_at, created_at, updated_at, lock_version)
                values
                    (:id, :definition_id, 1, :entity_type, :entity_id, :instance_key, null,
                     :state_id, :started_at, :completed_at, :cancelled_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                """
            ),
            {
                "id": db_uuid(uuid4(), bind),
                "definition_id": db_uuid(definition_id, bind),
                "entity_type": ENTITY_TYPE,
                "entity_id": db_uuid(request_id, bind),
                "instance_key": INSTANCE_KEY,
                "state_id": db_uuid(state_ids[status_code], bind),
                "started_at": request["created_at"],
                "completed_at": request["completed_at"] if status_code in {"COMPLETED", "CLOSED"} else None,
                "cancelled_at": request["updated_at"] if status_code == "CANCELLED" else None,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    definition = bind.execute(
        sa.text("select id from workflow_definitions where code = :code and version = 1"),
        {"code": WORKFLOW_CODE},
    ).mappings().first()
    if definition is None:
        return
    definition_id = as_uuid(definition["id"])
    bind.execute(sa.text("delete from workflow_instances where workflow_definition_id = :definition_id"), {"definition_id": db_uuid(definition_id, bind)})
    bind.execute(sa.text("delete from workflow_sla_policies where workflow_definition_id = :definition_id"), {"definition_id": db_uuid(definition_id, bind)})
    bind.execute(sa.text("delete from workflow_transitions where workflow_definition_id = :definition_id"), {"definition_id": db_uuid(definition_id, bind)})
    bind.execute(sa.text("delete from workflow_states where workflow_definition_id = :definition_id"), {"definition_id": db_uuid(definition_id, bind)})
    bind.execute(sa.text("delete from workflow_definitions where id = :definition_id"), {"definition_id": db_uuid(definition_id, bind)})
