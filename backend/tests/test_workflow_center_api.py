from collections.abc import Generator
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AuthSource, Role, User, UserRole, UserType
from app.models.requests import ContractorRequest, RequestStatus
from app.models.workflow import (
    DomainEventOutbox,
    DomainEventStatus,
    DomainEventType,
    WorkflowActorType,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowState,
    WorkflowSlaPolicy,
    WorkflowSlaStatus,
    WorkflowSlaTimer,
    WorkflowStateType,
    WorkflowTransition,
    WorkflowTransitionExecution,
)
from app.models.reference_data import utc_now
from app.services.contractor_request_workflow import CONTRACTOR_REQUEST_ENTITY_TYPE, CONTRACTOR_REQUEST_WORKFLOW_CODE, seed_contractor_request_workflow_definition
from app.services.rbac_service import seed_rbac


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
        seed_contractor_request_workflow_definition(session)
        seed_workflow_center_fixture(session)
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-User-Role": "PLATFORM_ADMIN"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_user_with_role(db: Session, role_code: str) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    user = User(
        username=f"{role_code.lower()}-{uuid4()}",
        display_name=role.name,
        user_type=UserType.CONTRACTOR if role_code.startswith("CONTRACTOR") else UserType.INTERNAL,
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


@pytest.fixture()
def platform_admin_headers(db_session: Session) -> dict[str, str]:
    user = create_user_with_role(db_session, "PLATFORM_ADMIN")
    return {"X-User-Id": str(user.id)}


def create_draft(client: TestClient, headers: dict[str, str], *, code: str | None = None) -> dict:
    response = client.post(
        "/api/v1/admin/workflow-center/definitions",
        headers=headers,
        json={
            "code": code or f"TEST_FLOW_{uuid4().hex}",
            "name": "Test workflow",
            "description": "Draft workflow",
            "entity_type": "TEST_ENTITY",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_published"] is False
    return body


def add_state(client: TestClient, headers: dict[str, str], definition_id: str, *, code: str, initial: bool = False, terminal: bool = False) -> dict:
    response = client.post(
        f"/api/v1/admin/workflow-center/definitions/{definition_id}/states",
        headers=headers,
        json={
            "code": code,
            "name": code.title(),
            "state_type": WorkflowStateType.INITIAL.value if initial else WorkflowStateType.COMPLETED.value if terminal else WorkflowStateType.ACTIVE.value,
            "is_initial": initial,
            "is_terminal": terminal,
            "sort_order": 10 if initial else 20,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def add_transition(client: TestClient, headers: dict[str, str], definition_id: str, from_state_id: str, to_state_id: str, *, code: str = "SUBMIT") -> dict:
    response = client.post(
        f"/api/v1/admin/workflow-center/definitions/{definition_id}/transitions",
        headers=headers,
        json={
            "code": code,
            "name": "Submit",
            "from_state_id": from_state_id,
            "to_state_id": to_state_id,
            "permission_code": "workflows.instances.transition",
            "configuration_json": {"allowed_permissions": ["workflows.instances.transition"]},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_publishable_draft(client: TestClient, headers: dict[str, str]) -> dict:
    draft = create_draft(client, headers)
    detail = add_state(client, headers, draft["id"], code="DRAFT", initial=True)
    initial = next(state for state in detail["states"] if state["code"] == "DRAFT")
    detail = add_state(client, headers, draft["id"], code="DONE", terminal=True)
    done = next(state for state in detail["states"] if state["code"] == "DONE")
    return add_transition(client, headers, draft["id"], initial["id"], done["id"])


def seed_workflow_center_fixture(db: Session) -> None:
    definition = db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE))
    assert definition is not None
    states = list(db.scalars(select(WorkflowState).where(WorkflowState.workflow_definition_id == definition.id).order_by(WorkflowState.sort_order)))
    transitions = list(db.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_definition_id == definition.id).order_by(WorkflowTransition.sort_order)))
    assert len(states) >= 2
    assert transitions

    request = ContractorRequest(
        request_number="CR-WFC-001",
        title="Workflow Center fixture",
        description="Workflow Center fixture",
        status=RequestStatus.NEW,
    )
    db.add(request)
    db.flush()

    instance = WorkflowInstance(
        workflow_definition_id=definition.id,
        workflow_version=definition.version,
        entity_type=CONTRACTOR_REQUEST_ENTITY_TYPE,
        entity_id=request.id,
        instance_key="default",
        current_state_id=states[1].id,
    )
    db.add(instance)
    db.flush()

    execution = WorkflowTransitionExecution(
        workflow_instance_id=instance.id,
        transition_id=transitions[0].id,
        from_state_id=transitions[0].from_state_id,
        to_state_id=transitions[0].to_state_id,
        actor_type=WorkflowActorType.INTERNAL_USER,
        comment="visible comment",
        correlation_id="corr-workflow-center",
    )
    db.add(execution)

    policy = WorkflowSlaPolicy(
        workflow_definition_id=definition.id,
        state_id=states[1].id,
        code="CENTER_FIXTURE_SLA",
        name="Center fixture SLA",
        duration_minutes=60,
        warning_before_minutes=15,
    )
    db.add(policy)
    db.flush()
    db.add(
        WorkflowSlaTimer(
            workflow_instance_id=instance.id,
            sla_policy_id=policy.id,
            started_at=utc_now(),
            due_at=utc_now() + timedelta(hours=1),
            warning_at=utc_now() + timedelta(minutes=45),
            status=WorkflowSlaStatus.ACTIVE,
        )
    )
    db.add(
        DomainEventOutbox(
            event_type=DomainEventType.WORKFLOW_STARTED.value,
            aggregate_type=CONTRACTOR_REQUEST_ENTITY_TYPE,
            aggregate_id=request.id,
            payload={"correlation_id": "corr-workflow-center", "secret_token": "must-not-leak"},
            status=DomainEventStatus.PENDING,
        )
    )
    db.commit()


def test_dashboard_definitions_instances_and_monitors(client: TestClient) -> None:
    for path in [
        "/api/v1/admin/workflow-center/dashboard",
        "/api/v1/admin/workflow-center/definitions",
        "/api/v1/admin/workflow-center/instances",
        "/api/v1/admin/workflow-center/sla",
        "/api/v1/admin/workflow-center/outbox",
        "/api/v1/admin/workflow-center/audit",
        "/api/v1/admin/workflow-center/statistics",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path


def test_every_declared_workflow_center_endpoint_has_permission_and_schema() -> None:
    routes: list[tuple[str, APIRoute]] = []
    for included in app.routes:
        if not hasattr(included, "original_router"):
            continue
        prefix = included.include_context.prefix
        for route in included.original_router.routes:
            if isinstance(route, APIRoute):
                full_path = f"{prefix}{route.path}"
                if full_path.startswith("/api/v1/admin/workflow-center"):
                    routes.append((full_path, route))
    methods = {(next(iter(route.methods - {"HEAD", "OPTIONS"})), path) for path, route in routes}
    expected = {
        ("GET", "/api/v1/admin/workflow-center/dashboard"),
        ("GET", "/api/v1/admin/workflow-center/definitions"),
        ("POST", "/api/v1/admin/workflow-center/definitions"),
        ("GET", "/api/v1/admin/workflow-center/definitions/{definition_id}"),
        ("PATCH", "/api/v1/admin/workflow-center/definitions/{definition_id}"),
        ("POST", "/api/v1/admin/workflow-center/definitions/{definition_id}/versions"),
        ("POST", "/api/v1/admin/workflow-center/definitions/{definition_id}/publish"),
        ("POST", "/api/v1/admin/workflow-center/definitions/{definition_id}/deactivate"),
        ("POST", "/api/v1/admin/workflow-center/definitions/{definition_id}/states"),
        ("PATCH", "/api/v1/admin/workflow-center/definitions/{definition_id}/states/{state_id}"),
        ("POST", "/api/v1/admin/workflow-center/definitions/{definition_id}/transitions"),
        ("PATCH", "/api/v1/admin/workflow-center/definitions/{definition_id}/transitions/{transition_id}"),
        ("POST", "/api/v1/admin/workflow-center/definitions/{definition_id}/sla"),
        ("PATCH", "/api/v1/admin/workflow-center/definitions/{definition_id}/sla/{sla_id}"),
        ("GET", "/api/v1/admin/workflow-center/definitions/{definition_id}/validation"),
        ("GET", "/api/v1/admin/workflow-center/versions"),
        ("GET", "/api/v1/admin/workflow-center/versions/diff"),
        ("GET", "/api/v1/admin/workflow-center/instances"),
        ("GET", "/api/v1/admin/workflow-center/instances/{instance_id}"),
        ("GET", "/api/v1/admin/workflow-center/sla"),
        ("GET", "/api/v1/admin/workflow-center/outbox"),
        ("GET", "/api/v1/admin/workflow-center/audit"),
        ("GET", "/api/v1/admin/workflow-center/statistics"),
        ("GET", "/api/v1/admin/workflow-center/health"),
        ("GET", "/api/v1/admin/workflow-center/definitions/{definition_id}/export"),
        ("GET", "/api/v1/admin/workflow-center/search"),
    }
    assert expected <= methods
    for path, route in routes:
        dependency_names = {dependency.call.__name__ for dependency in route.dependant.dependencies if dependency.call}
        assert "dependency" in dependency_names or "require_csrf" in dependency_names
        if not path.endswith("/export"):
            assert route.response_model is not None
        if route.methods & {"POST", "PATCH", "PUT", "DELETE"}:
            assert "require_csrf" in dependency_names


def test_definition_detail_validation_export_and_search(client: TestClient, db_session: Session) -> None:
    definition = db_session.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE))
    assert definition is not None

    detail = client.get(f"/api/v1/admin/workflow-center/definitions/{definition.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["code"] == CONTRACTOR_REQUEST_WORKFLOW_CODE
    assert body["states_count"] >= 1
    assert body["transitions_count"] >= 1
    assert body["validation"]["status"] in {"ok", "warning", "error"}

    validation = client.get(f"/api/v1/admin/workflow-center/definitions/{definition.id}/validation")
    assert validation.status_code == 200
    assert "errors" in validation.json()

    exported = client.get(f"/api/v1/admin/workflow-center/definitions/{definition.id}/export")
    assert exported.status_code == 200
    assert exported.json()["id"] == str(definition.id)

    search = client.get("/api/v1/admin/workflow-center/search", params={"q": "CR-WFC"})
    assert search.status_code == 200
    assert any(item["label"] == "CR-WFC-001" for item in search.json()["items"])


def test_create_draft_add_edit_state_and_validation_errors(client: TestClient, platform_admin_headers: dict[str, str]) -> None:
    draft = create_draft(client, platform_admin_headers)
    validation = client.get(f"/api/v1/admin/workflow-center/definitions/{draft['id']}/validation")
    assert validation.status_code == 200
    assert validation.json()["status"] == "error"
    assert any(issue["code"] == "initial_state" for issue in validation.json()["errors"])

    detail = add_state(client, platform_admin_headers, draft["id"], code="DRAFT", initial=True)
    state = next(item for item in detail["states"] if item["code"] == "DRAFT")
    response = client.patch(
        f"/api/v1/admin/workflow-center/definitions/{draft['id']}/states/{state['id']}",
        headers=platform_admin_headers,
        json={"name": "Draft Updated", "sort_order": 5},
    )
    assert response.status_code == 200
    updated = next(item for item in response.json()["states"] if item["id"] == state["id"])
    assert updated["name"] == "Draft Updated"


def test_add_edit_transition_and_unsafe_configuration_rejected(client: TestClient, platform_admin_headers: dict[str, str]) -> None:
    draft = create_draft(client, platform_admin_headers)
    detail = add_state(client, platform_admin_headers, draft["id"], code="DRAFT", initial=True)
    initial = next(state for state in detail["states"] if state["code"] == "DRAFT")
    detail = add_state(client, platform_admin_headers, draft["id"], code="DONE", terminal=True)
    done = next(state for state in detail["states"] if state["code"] == "DONE")

    unsafe = client.post(
        f"/api/v1/admin/workflow-center/definitions/{draft['id']}/transitions",
        headers=platform_admin_headers,
        json={
            "code": "UNSAFE",
            "name": "Unsafe",
            "from_state_id": initial["id"],
            "to_state_id": done["id"],
            "configuration_json": {"secret_token": "nope"},
        },
    )
    assert unsafe.status_code == 422

    detail = add_transition(client, platform_admin_headers, draft["id"], initial["id"], done["id"])
    transition = next(item for item in detail["transitions"] if item["code"] == "SUBMIT")
    response = client.patch(
        f"/api/v1/admin/workflow-center/definitions/{draft['id']}/transitions/{transition['id']}",
        headers=platform_admin_headers,
        json={"name": "Submit Updated", "requires_comment": True},
    )
    assert response.status_code == 200
    updated = next(item for item in response.json()["transitions"] if item["id"] == transition["id"])
    assert updated["name"] == "Submit Updated"
    assert updated["requires_comment"] is True


def test_valid_publish_published_immutability_and_new_version_creation(client: TestClient, platform_admin_headers: dict[str, str]) -> None:
    detail = make_publishable_draft(client, platform_admin_headers)
    definition_id = detail["id"]
    publish = client.post(f"/api/v1/admin/workflow-center/definitions/{definition_id}/publish", headers=platform_admin_headers)
    assert publish.status_code == 200
    assert publish.json()["is_published"] is True

    immutable = client.patch(
        f"/api/v1/admin/workflow-center/definitions/{definition_id}",
        headers=platform_admin_headers,
        json={"name": "Should not change"},
    )
    assert immutable.status_code == 409

    state_id = publish.json()["states"][0]["id"]
    assert client.patch(f"/api/v1/admin/workflow-center/definitions/{definition_id}/states/{state_id}", headers=platform_admin_headers, json={"name": "No"}).status_code == 409

    version = client.post(f"/api/v1/admin/workflow-center/definitions/{definition_id}/versions", headers=platform_admin_headers)
    assert version.status_code == 200
    assert version.json()["version"] == publish.json()["version"] + 1
    assert version.json()["is_published"] is False


def test_sla_crud(client: TestClient, platform_admin_headers: dict[str, str]) -> None:
    detail = make_publishable_draft(client, platform_admin_headers)
    definition_id = detail["id"]
    done = next(state for state in detail["states"] if state["code"] == "DONE")
    response = client.post(
        f"/api/v1/admin/workflow-center/definitions/{definition_id}/sla",
        headers=platform_admin_headers,
        json={
            "state_id": done["id"],
            "code": "DONE_SLA",
            "name": "Done SLA",
            "duration_minutes": 120,
            "warning_before_minutes": 30,
            "severity": "WARNING",
        },
    )
    assert response.status_code == 200
    policy = next(item for item in response.json()["sla_policies"] if item["code"] == "DONE_SLA")
    update = client.patch(
        f"/api/v1/admin/workflow-center/definitions/{definition_id}/sla/{policy['id']}",
        headers=platform_admin_headers,
        json={"name": "Done SLA Updated", "duration_minutes": 180, "is_active": False},
    )
    assert update.status_code == 200
    updated = next(item for item in update.json()["sla_policies"] if item["id"] == policy["id"])
    assert updated["name"] == "Done SLA Updated"
    assert updated["duration_minutes"] == 180
    assert updated["is_active"] is False


def test_instance_detail_uses_business_identifier_and_hides_raw_payload(client: TestClient, db_session: Session) -> None:
    instance = db_session.scalar(select(WorkflowInstance))
    assert instance is not None

    response = client.get(f"/api/v1/admin/workflow-center/instances/{instance.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["business_identifier"] == "CR-WFC-001"
    assert body["executions"][0]["correlation_id"] == "corr-workflow-center"
    assert body["outbox_events"][0]["correlation_id"] == "corr-workflow-center"
    assert "payload" not in body["outbox_events"][0]
    assert "secret_token" not in str(body)

    outbox = client.get("/api/v1/admin/workflow-center/outbox")
    assert outbox.status_code == 200
    assert "payload" not in str(outbox.json())
    assert "secret_token" not in str(outbox.json())


def test_workflow_instance_list_and_detail(client: TestClient) -> None:
    listed = client.get("/api/v1/admin/workflow-center/instances", params={"search": "CR-WFC"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["business_identifier"] == "CR-WFC-001"

    detail = client.get(f"/api/v1/admin/workflow-center/instances/{items[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == items[0]["id"]
    assert detail.json()["executions"]


def test_contractor_access_denied(db_session: Session) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-User-Role": "CONTRACTOR_USER"}) as contractor:
        for path in [
            "/api/v1/admin/workflow-center/dashboard",
            "/api/v1/admin/workflow-center/definitions",
            "/api/v1/admin/workflow-center/instances",
            "/api/v1/admin/workflow-center/outbox",
        ]:
            assert contractor.get(path).status_code == 403, path
    app.dependency_overrides.clear()


def test_security_operator_operational_read_only_access(db_session: Session) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-User-Role": "SECURITY_OPERATOR"}) as operator:
        assert operator.get("/api/v1/admin/workflow-center/dashboard").status_code == 200
        assert operator.get("/api/v1/admin/workflow-center/instances").status_code == 200
        assert operator.get("/api/v1/admin/workflow-center/outbox").status_code == 200
        assert operator.get("/api/v1/admin/workflow-center/statistics").status_code == 200
        assert operator.get("/api/v1/admin/workflow-center/definitions").status_code == 403
        assert operator.get("/api/v1/admin/workflow-center/sla").status_code == 403
        assert operator.post("/api/v1/admin/workflow-center/definitions", json={"code": "DENY", "name": "Deny", "entity_type": "DENY"}).status_code == 403
    app.dependency_overrides.clear()


def test_csrf_is_required_on_every_mutation(client: TestClient, platform_admin_headers: dict[str, str]) -> None:
    detail = make_publishable_draft(client, platform_admin_headers)
    definition_id = detail["id"]
    state = next(item for item in detail["states"] if item["code"] == "DRAFT")
    transition = next(item for item in detail["transitions"] if item["code"] == "SUBMIT")
    sla_response = client.post(
        f"/api/v1/admin/workflow-center/definitions/{definition_id}/sla",
        headers=platform_admin_headers,
        json={"state_id": state["id"], "code": "SLA", "name": "SLA", "duration_minutes": 60},
    )
    assert sla_response.status_code == 200
    sla = sla_response.json()["sla_policies"][0]
    missing_csrf_headers = {"X-User-Role": "PLATFORM_ADMIN"}
    cases = [
        ("post", "/api/v1/admin/workflow-center/definitions", {"code": "NO_CSRF", "name": "No CSRF", "entity_type": "TEST"}),
        ("patch", f"/api/v1/admin/workflow-center/definitions/{definition_id}", {"name": "No CSRF"}),
        ("post", f"/api/v1/admin/workflow-center/definitions/{definition_id}/versions", None),
        ("post", f"/api/v1/admin/workflow-center/definitions/{definition_id}/publish", None),
        ("post", f"/api/v1/admin/workflow-center/definitions/{definition_id}/deactivate", None),
        ("post", f"/api/v1/admin/workflow-center/definitions/{definition_id}/states", {"code": "X", "name": "X", "state_type": "ACTIVE"}),
        ("patch", f"/api/v1/admin/workflow-center/definitions/{definition_id}/states/{state['id']}", {"name": "X"}),
        ("post", f"/api/v1/admin/workflow-center/definitions/{definition_id}/transitions", {"code": "X", "name": "X", "from_state_id": state["id"], "to_state_id": state["id"]}),
        ("patch", f"/api/v1/admin/workflow-center/definitions/{definition_id}/transitions/{transition['id']}", {"name": "X"}),
        ("post", f"/api/v1/admin/workflow-center/definitions/{definition_id}/sla", {"code": "X", "name": "X", "duration_minutes": 1}),
        ("patch", f"/api/v1/admin/workflow-center/definitions/{definition_id}/sla/{sla['id']}", {"name": "X"}),
    ]
    for method, path, payload in cases:
        response = getattr(client, method)(path, headers=missing_csrf_headers, json=payload)
        assert response.status_code in {401, 403}, path


def test_contractor_request_v1_is_protected_and_preserves_statuses(client: TestClient, db_session: Session, platform_admin_headers: dict[str, str]) -> None:
    definition = db_session.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE, WorkflowDefinition.version == 1))
    assert definition is not None
    detail = client.get(f"/api/v1/admin/workflow-center/definitions/{definition.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["is_published"] is True
    assert [state["code"] for state in body["states"]] == [
        "DRAFT",
        "NEW",
        "PARTIALLY_ASSIGNED",
        "ASSIGNED",
        "IN_PROGRESS",
        "COMPLETED",
        "CLOSED",
        "CANCELLED",
    ]

    assert client.patch(f"/api/v1/admin/workflow-center/definitions/{definition.id}", headers=platform_admin_headers, json={"name": "No"}).status_code == 409
    assert client.post(f"/api/v1/admin/workflow-center/definitions/{definition.id}/versions", headers=platform_admin_headers).status_code == 409
    assert client.post(f"/api/v1/admin/workflow-center/definitions/{definition.id}/deactivate", headers=platform_admin_headers).status_code == 409

    state = body["states"][0]
    assert client.patch(f"/api/v1/admin/workflow-center/definitions/{definition.id}/states/{state['id']}", headers=platform_admin_headers, json={"name": "No"}).status_code == 409


def test_permissions_are_enforced_for_definition_pages(db_session: Session) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-User-Role": "VIEWER"}) as viewer:
        response = viewer.get("/api/v1/admin/workflow-center/definitions")
        assert response.status_code == 403
        instances = viewer.get("/api/v1/admin/workflow-center/instances")
        assert instances.status_code == 200
    app.dependency_overrides.clear()
