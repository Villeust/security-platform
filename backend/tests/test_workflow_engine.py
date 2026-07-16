from collections.abc import Generator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.admin import AdminAuditLog, AuthSource, Permission, Role, User, UserRole, UserType
from app.models.reference_data import utc_now
from app.models.workflow import (
    DomainEventOutbox,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowSlaTimer,
    WorkflowStateType,
    WorkflowTransitionExecution,
)
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowSlaPolicyCreate,
    WorkflowStateCreate,
    WorkflowTransitionCreate,
)
from app.services.rbac_service import permission_codes_for_user, seed_rbac
from app.services.workflow_adapters import WorkflowActor, WorkflowEntityAdapter, workflow_adapters
from app.services.workflow_definition_service import (
    add_sla_policy,
    add_workflow_state,
    add_workflow_transition,
    create_workflow_definition,
    create_workflow_version,
    publish_workflow_definition,
    update_workflow_definition,
)
from app.services.workflow_engine import (
    execute_transition,
    get_available_transitions,
    mark_breached_sla_timers,
    start_workflow,
)


TEST_ENTITY_TYPE = "TEST_ENTITY"


class DummyWorkflowAdapter(WorkflowEntityAdapter):
    entity_type = TEST_ENTITY_TYPE

    def __init__(self) -> None:
        self.entities: set[UUID] = set()
        self.inaccessible: set[UUID] = set()
        self.applied: list[str] = []

    def get_entity(self, db: Session, entity_id: UUID, actor: WorkflowActor) -> dict[str, Any]:
        if entity_id in self.inaccessible or entity_id not in self.entities:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"id": entity_id, "owner": actor.user.id}

    def validate_start(self, db: Session, entity: Any, actor: WorkflowActor) -> None:
        if actor.actor_type != "INTERNAL_USER":
            raise HTTPException(status_code=403, detail="Unsupported actor")

    def validate_transition(self, db: Session, entity: Any, transition, actor: WorkflowActor, input_data: dict | None) -> None:
        if input_data and input_data.get("deny"):
            raise HTTPException(status_code=409, detail="Adapter precondition failed")

    def apply_transition(self, db: Session, entity: Any, transition, actor: WorkflowActor, input_data: dict | None) -> dict:
        self.applied.append(transition.code)
        return {"transition": transition.code, "secret_token": "hidden", "nested": {"password": "hidden"}}

    def build_safe_context(self, entity: Any) -> dict:
        return {"entity_id": str(entity["id"])}


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as session:
        seed_rbac(session)
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def adapter() -> Generator[DummyWorkflowAdapter, None, None]:
    workflow_adapters.clear()
    item = DummyWorkflowAdapter()
    workflow_adapters.register(item)
    yield item
    workflow_adapters.clear()


def user_with_role(db: Session, role_code: str) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    user = User(
        username=f"{role_code.lower()}-{uuid4()}",
        display_name=role.name,
        user_type=UserType.INTERNAL,
        auth_source=AuthSource.LOCAL,
        is_active=True,
        is_locked=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def actor(db: Session, role_code: str = "PLATFORM_ADMIN", permissions: set[str] | None = None) -> WorkflowActor:
    user = user_with_role(db, role_code)
    return WorkflowActor(
        user=user,
        permissions=permissions if permissions is not None else permission_codes_for_user(user),
        actor_type="INTERNAL_USER",
    )


def create_definition(db: Session, *, publish: bool = True, with_sla: bool = False) -> tuple[WorkflowDefinition, dict[str, object]]:
    definition = create_workflow_definition(
        db,
        WorkflowDefinitionCreate(code=f"TEST_FLOW_{uuid4().hex}", name="Test workflow", entity_type=TEST_ENTITY_TYPE),
    )
    draft = add_workflow_state(
        db,
        definition.id,
        WorkflowStateCreate(code="DRAFT", name="Draft", state_type=WorkflowStateType.INITIAL, is_initial=True, sort_order=10),
    )
    active = add_workflow_state(
        db,
        definition.id,
        WorkflowStateCreate(code="ACTIVE", name="Active", state_type=WorkflowStateType.ACTIVE, sort_order=20),
    )
    done = add_workflow_state(
        db,
        definition.id,
        WorkflowStateCreate(code="DONE", name="Done", state_type=WorkflowStateType.COMPLETED, is_terminal=True, sort_order=30),
    )
    start = add_workflow_transition(
        db,
        definition.id,
        WorkflowTransitionCreate(
            code="START",
            name="Start",
            from_state_id=draft.id,
            to_state_id=active.id,
            permission_code="workflows.instances.transition",
            configuration_json={"allowed_actor_types": ["INTERNAL_USER"]},
        ),
    )
    finish = add_workflow_transition(
        db,
        definition.id,
        WorkflowTransitionCreate(
            code="FINISH",
            name="Finish",
            from_state_id=active.id,
            to_state_id=done.id,
            permission_code="workflows.instances.transition",
            requires_comment=True,
            configuration_json={"required_fields": ["resolution"]},
        ),
    )
    if with_sla:
        add_sla_policy(
            db,
            definition.id,
            WorkflowSlaPolicyCreate(
                state_id=draft.id,
                code="DRAFT_LIMIT",
                name="Draft limit",
                duration_minutes=60,
                warning_before_minutes=15,
            ),
        )
    if publish:
        publish_workflow_definition(db, definition.id)
    db.commit()
    db.refresh(definition)
    return definition, {"draft": draft, "active": active, "done": done, "start": start, "finish": finish}


def test_create_workflow_definition_and_versions(db_session: Session) -> None:
    first = create_workflow_definition(db_session, WorkflowDefinitionCreate(code="VERSIONED", name="Versioned", entity_type=TEST_ENTITY_TYPE))
    second = create_workflow_definition(db_session, WorkflowDefinitionCreate(code="VERSIONED", name="Versioned v2", entity_type=TEST_ENTITY_TYPE))

    assert first.version == 1
    assert second.version == 2
    assert db_session.scalar(select(func.count(WorkflowDefinition.id)).where(WorkflowDefinition.code == "VERSIONED")) == 2


def test_prevent_multiple_initial_states(db_session: Session) -> None:
    definition = create_workflow_definition(db_session, WorkflowDefinitionCreate(code="INITIAL_CHECK", name="Initial", entity_type=TEST_ENTITY_TYPE))
    add_workflow_state(db_session, definition.id, WorkflowStateCreate(code="ONE", name="One", state_type=WorkflowStateType.INITIAL, is_initial=True))

    with pytest.raises(HTTPException) as exc:
        add_workflow_state(db_session, definition.id, WorkflowStateCreate(code="TWO", name="Two", state_type=WorkflowStateType.INITIAL, is_initial=True))

    assert exc.value.status_code == 409


def test_publish_rejects_unreachable_state(db_session: Session) -> None:
    definition = create_workflow_definition(db_session, WorkflowDefinitionCreate(code="UNREACHABLE", name="Unreachable", entity_type=TEST_ENTITY_TYPE))
    add_workflow_state(db_session, definition.id, WorkflowStateCreate(code="START", name="Start", state_type=WorkflowStateType.INITIAL, is_initial=True))
    add_workflow_state(db_session, definition.id, WorkflowStateCreate(code="ORPHAN", name="Orphan", state_type=WorkflowStateType.ACTIVE))

    with pytest.raises(HTTPException) as exc:
        publish_workflow_definition(db_session, definition.id)

    assert exc.value.status_code == 422


def test_published_workflow_is_immutable_and_can_create_new_version(db_session: Session) -> None:
    definition, _ = create_definition(db_session)

    with pytest.raises(HTTPException) as exc:
        update_workflow_definition(db_session, definition.id, WorkflowDefinitionUpdate(name="Changed"))

    next_version = create_workflow_version(db_session, definition.id)
    assert exc.value.status_code == 409
    assert next_version.version == definition.version + 1
    assert next_version.is_published is False


def test_transition_configuration_rejects_unsafe_keys(db_session: Session) -> None:
    definition = create_workflow_definition(db_session, WorkflowDefinitionCreate(code="BAD_CONFIG", name="Bad config", entity_type=TEST_ENTITY_TYPE))
    first = add_workflow_state(db_session, definition.id, WorkflowStateCreate(code="FIRST", name="First", state_type=WorkflowStateType.INITIAL, is_initial=True))
    second = add_workflow_state(db_session, definition.id, WorkflowStateCreate(code="SECOND", name="Second", state_type=WorkflowStateType.ACTIVE))

    with pytest.raises(HTTPException) as exc:
        add_workflow_transition(
            db_session,
            definition.id,
            WorkflowTransitionCreate(
                code="BAD",
                name="Bad",
                from_state_id=first.id,
                to_state_id=second.id,
                configuration_json={"python_import": "os.system"},
            ),
        )

    assert exc.value.status_code == 422


def test_start_workflow_creates_instance_sla_outbox_and_audit(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session, with_sla=True)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session)

    instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
    db_session.commit()

    assert instance.workflow_version == definition.version
    assert instance.instance_key == "default"
    assert db_session.scalar(select(WorkflowSlaTimer).where(WorkflowSlaTimer.workflow_instance_id == instance.id)) is not None
    assert db_session.scalar(select(DomainEventOutbox).where(DomainEventOutbox.event_type == "WORKFLOW_STARTED")) is not None
    assert db_session.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "WORKFLOW_STARTED")) is not None


def test_available_transitions_respect_permissions(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    allowed = actor(db_session, permissions={"workflows.instances.transition"})
    denied = actor(db_session, permissions=set())
    instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, allowed, workflow_code=definition.code)

    assert [item.code for item in get_available_transitions(db_session, instance, allowed)] == ["START"]
    assert get_available_transitions(db_session, instance, denied) == []


def test_execute_transition_updates_state_history_audit_outbox_and_sanitizes_data(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, states = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session, permissions={"workflows.instances.transition"})
    instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)

    execution = execute_transition(
        db_session,
        TEST_ENTITY_TYPE,
        entity_id,
        "START",
        current_actor,
        input_data={"token": "unsafe", "visible": "ok"},
        lock_version=1,
        workflow_code=definition.code,
    )
    db_session.commit()
    db_session.refresh(instance)

    assert execution.from_state_id == states["draft"].id
    assert execution.to_state_id == states["active"].id
    assert execution.input_data == {"token": "***", "visible": "ok"}
    assert execution.safe_result_data["secret_token"] == "***"
    assert execution.safe_result_data["nested"]["password"] == "***"
    assert instance.current_state_id == states["active"].id
    assert instance.lock_version == 2
    assert db_session.scalar(select(WorkflowTransitionExecution).where(WorkflowTransitionExecution.workflow_instance_id == instance.id)) is not None
    assert db_session.scalar(select(DomainEventOutbox).where(DomainEventOutbox.event_type == "WORKFLOW_TRANSITION_EXECUTED")) is not None
    assert db_session.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "WORKFLOW_TRANSITION_EXECUTED")) is not None


def test_stale_lock_version_returns_conflict(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session, permissions={"workflows.instances.transition"})
    start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)

    with pytest.raises(HTTPException) as exc:
        execute_transition(db_session, TEST_ENTITY_TYPE, entity_id, "START", current_actor, lock_version=99, workflow_code=definition.code)

    assert exc.value.status_code == 409


def test_idempotent_retry_does_not_duplicate_execution(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session, permissions={"workflows.instances.transition"})
    instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)

    first = execute_transition(db_session, TEST_ENTITY_TYPE, entity_id, "START", current_actor, idempotency_key="same-key", workflow_code=definition.code)
    second = execute_transition(db_session, TEST_ENTITY_TYPE, entity_id, "START", current_actor, idempotency_key="same-key", workflow_code=definition.code)

    assert first.id == second.id
    assert db_session.scalar(select(func.count(WorkflowTransitionExecution.id)).where(WorkflowTransitionExecution.workflow_instance_id == instance.id)) == 1


def test_idempotency_key_reuse_with_different_payload_returns_conflict(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session, permissions={"workflows.instances.transition"})
    start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
    execute_transition(db_session, TEST_ENTITY_TYPE, entity_id, "START", current_actor, idempotency_key="same-key", workflow_code=definition.code)

    with pytest.raises(HTTPException) as exc:
        execute_transition(
            db_session,
            TEST_ENTITY_TYPE,
            entity_id,
            "START",
            current_actor,
            input_data={"different": True},
            idempotency_key="same-key",
            workflow_code=definition.code,
        )

    assert exc.value.status_code == 409


def test_terminal_workflow_cannot_transition(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session, permissions={"workflows.instances.transition"})
    instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
    execute_transition(db_session, TEST_ENTITY_TYPE, entity_id, "START", current_actor, workflow_code=definition.code)
    execute_transition(
        db_session,
        TEST_ENTITY_TYPE,
        entity_id,
        "FINISH",
        current_actor,
        comment="Done",
        input_data={"resolution": "ok"},
        workflow_code=definition.code,
    )
    db_session.refresh(instance)

    assert get_available_transitions(db_session, instance, current_actor) == []
    with pytest.raises(HTTPException) as exc:
        execute_transition(db_session, TEST_ENTITY_TYPE, entity_id, "FINISH", current_actor, comment="Again", input_data={"resolution": "ok"}, workflow_code=definition.code)
    assert exc.value.status_code == 409


def test_sla_timer_completion_and_breach(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session, with_sla=True)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session, permissions={"workflows.instances.transition"})
    instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
    timer = db_session.scalar(select(WorkflowSlaTimer).where(WorkflowSlaTimer.workflow_instance_id == instance.id))
    assert timer is not None
    timer.due_at = utc_now()

    breached = mark_breached_sla_timers(db_session, utc_now())
    assert breached == 1
    assert timer.status == "BREACHED"
    assert db_session.scalar(select(DomainEventOutbox).where(DomainEventOutbox.event_type == "SLA_BREACHED")) is not None


def test_unknown_and_inaccessible_adapters_return_404(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    current_actor = actor(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    adapter.inaccessible.add(entity_id)

    with pytest.raises(HTTPException) as inaccessible:
        start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
    with pytest.raises(HTTPException) as unknown:
        start_workflow(db_session, "UNKNOWN_ENTITY", uuid4(), current_actor)

    assert inaccessible.value.status_code == 404
    assert unknown.value.status_code == 404


def test_parallel_instance_keys_for_same_entity_are_allowed(db_session: Session, adapter: DummyWorkflowAdapter) -> None:
    definition, _ = create_definition(db_session)
    entity_id = uuid4()
    adapter.entities.add(entity_id)
    current_actor = actor(db_session)

    first = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
    second = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code, instance_key="secondary")

    assert first.id != second.id
    assert db_session.scalar(select(func.count(WorkflowInstance.id)).where(WorkflowInstance.entity_id == entity_id)) == 2


def test_workflow_permissions_are_seeded(db_session: Session) -> None:
    codes = set(db_session.scalars(select(Permission.code).where(Permission.code.like("workflows.%"))).all())
    admin = user_with_role(db_session, "PLATFORM_ADMIN")
    operator = user_with_role(db_session, "SECURITY_OPERATOR")
    contractor_role = db_session.scalar(select(Role).where(Role.code == "CONTRACTOR_USER"))

    assert {
        "workflows.view",
        "workflows.manage",
        "workflows.publish",
        "workflows.instances.view",
        "workflows.instances.transition",
        "workflows.sla.view",
        "workflows.sla.manage",
    }.issubset(codes)
    assert "workflows.manage" in permission_codes_for_user(admin)
    assert "workflows.instances.transition" in permission_codes_for_user(operator)
    assert contractor_role is not None
