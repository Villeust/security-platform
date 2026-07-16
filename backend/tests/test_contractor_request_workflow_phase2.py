from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AuthSource, ContractorMembership, Role, User, UserRole, UserType
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType
from app.models.requests import ContractorRequest, RequestHistory, RequestStatus
from app.models.workflow import DomainEventOutbox, WorkflowDefinition, WorkflowInstance, WorkflowState, WorkflowTransition, WorkflowTransitionExecution
from app.services.contractor_request_workflow import (
    APPROVED_REQUEST_STATE_CODES,
    CONTRACTOR_REQUEST_ENTITY_TYPE,
    CONTRACTOR_REQUEST_WORKFLOW_CODE,
    REQUEST_TRANSITION_CODES,
    backfill_contractor_request_workflow_instances,
    seed_contractor_request_workflow_definition,
)
from app.services.password_service import password_hasher
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


@pytest.fixture()
def storage_root(tmp_path) -> Generator[str, None, None]:  # type: ignore[no-untyped-def]
    original = settings.storage_root
    settings.storage_root = str(tmp_path)
    yield str(tmp_path)
    settings.storage_root = original


def seed_refs(db: Session) -> dict[str, object]:
    city = City(name=f"City {uuid4()}", code=f"CITY-{uuid4()}")
    facility = Facility(city=city, name="Facility", address="Address", code=f"FAC-{uuid4()}")
    premise = Premise(facility=facility, name="Premise", has_access_control=True)
    contractor_a = Contractor(name="Contractor A", code=f"A-{uuid4()}")
    contractor_b = Contractor(name="Contractor B", code=f"B-{uuid4()}")
    access = WorkType(name="Access", code=f"ACCESS-{uuid4()}", requires_premise=True)
    cctv = WorkType(name="CCTV", code=f"CCTV-{uuid4()}", requires_premise=False)
    db.add_all([city, facility, premise, contractor_a, contractor_b, access, cctv])
    db.commit()
    for item in (city, facility, premise, contractor_a, contractor_b, access, cctv):
        db.refresh(item)
    return {"city": city, "facility": facility, "premise": premise, "contractor_a": contractor_a, "contractor_b": contractor_b, "access": access, "cctv": cctv}


def add_responsibility(db: Session, contractor: Contractor, work_type: WorkType, facility: Facility) -> None:
    db.add(ContractorResponsibility(contractor_id=contractor.id, facility_id=facility.id, work_type_id=work_type.id))
    db.commit()


def request_payload(refs: dict[str, object], work_types: list[WorkType], *, premise: bool = False, save_as_draft: bool = False) -> dict:
    city = refs["city"]
    facility = refs["facility"]
    premise_obj = refs["premise"]
    assert isinstance(city, City) and isinstance(facility, Facility) and isinstance(premise_obj, Premise)
    payload = {
        "city_id": str(city.id),
        "facility_id": str(facility.id),
        "title": "Workflow parity request",
        "description": "Workflow parity request.",
        "work_type_ids": [str(work_type.id) for work_type in work_types],
        "save_as_draft": save_as_draft,
    }
    if premise:
        payload["premise_id"] = str(premise_obj.id)
    return payload


def create_request(client: TestClient, refs: dict[str, object], work_types: list[WorkType], *, premise: bool = False, save_as_draft: bool = False) -> dict:
    response = client.post("/api/v1/requests", json=request_payload(refs, work_types, premise=premise, save_as_draft=save_as_draft))
    assert response.status_code == 201
    return response.json()


def workflow_instance(db: Session, request_id: str) -> WorkflowInstance:
    entity_id = UUID(request_id)
    instance = db.scalar(
        select(WorkflowInstance)
        .join(WorkflowDefinition)
        .where(
            WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE,
            WorkflowInstance.entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE,
            WorkflowInstance.entity_id == entity_id,
            WorkflowInstance.instance_key == "default",
        )
    )
    assert instance is not None
    return instance


def workflow_state_code(db: Session, request_id: str) -> str:
    instance = workflow_instance(db, request_id)
    state = db.get(WorkflowState, instance.current_state_id)
    assert state is not None
    return state.code


def create_user_with_role(db: Session, role_code: str, contractor: Contractor | None = None) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    user = User(
        username=f"{role_code.lower()}-{uuid4()}",
        display_name=role.name,
        user_type=UserType.CONTRACTOR if role_code.startswith("CONTRACTOR") else UserType.INTERNAL,
        auth_source=AuthSource.LOCAL,
        is_active=True,
        is_locked=False,
        authentication_enabled=True,
        password_hash=password_hasher.hash("Talan7680!"),
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    if contractor is not None:
        db.add(ContractorMembership(user_id=user.id, contractor_id=contractor.id, is_primary=True, is_active=True))
    db.commit()
    db.refresh(user)
    return user


def test_contractor_request_workflow_seed_is_idempotent(db_session: Session) -> None:
    first = seed_contractor_request_workflow_definition(db_session)
    second = seed_contractor_request_workflow_definition(db_session)
    states = db_session.scalars(select(WorkflowState.code).where(WorkflowState.workflow_definition_id == first.id).order_by(WorkflowState.sort_order)).all()
    transitions = db_session.scalars(select(WorkflowTransition.code).where(WorkflowTransition.workflow_definition_id == first.id)).all()

    assert first.id == second.id
    assert states == APPROVED_REQUEST_STATE_CODES
    assert set(transitions) == set(REQUEST_TRANSITION_CODES.values())
    assert db_session.scalar(select(func.count(WorkflowDefinition.id)).where(WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE)) == 1


def test_backfill_existing_request_is_idempotent_and_preserves_legacy_data(client: TestClient, db_session: Session) -> None:
    refs = seed_refs(db_session)
    request = create_request(client, refs, [refs["cctv"]], save_as_draft=True)  # type: ignore[list-item]
    request_uuid = UUID(request["id"])
    history_count = db_session.scalar(select(func.count(RequestHistory.id)).where(RequestHistory.request_id == request_uuid))
    db_session.query(WorkflowInstance).delete()
    db_session.commit()

    first = backfill_contractor_request_workflow_instances(db_session)
    second = backfill_contractor_request_workflow_instances(db_session)
    saved = db_session.get(ContractorRequest, UUID(request["id"]))

    assert first["created"] == 1
    assert second["created"] == 0
    assert saved is not None and saved.status == RequestStatus.DRAFT
    assert db_session.scalar(select(func.count(RequestHistory.id)).where(RequestHistory.request_id == request_uuid)) == history_count
    assert workflow_state_code(db_session, request["id"]) == "DRAFT"


def test_new_draft_creates_workflow_instance(client: TestClient, db_session: Session) -> None:
    refs = seed_refs(db_session)
    request = create_request(client, refs, [refs["cctv"]], save_as_draft=True)  # type: ignore[list-item]

    assert request["status"] == "DRAFT"
    assert workflow_state_code(db_session, request["id"]) == "DRAFT"


def test_publish_partial_and_full_assignment_synchronize(client: TestClient, db_session: Session) -> None:
    refs = seed_refs(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access"], refs["facility"])  # type: ignore[arg-type]
    partial = create_request(client, refs, [refs["access"], refs["cctv"]], premise=True)  # type: ignore[list-item]
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], refs["facility"])  # type: ignore[arg-type]
    full = create_request(client, refs, [refs["cctv"]])  # type: ignore[list-item]

    assert partial["status"] == "PARTIALLY_ASSIGNED"
    assert full["status"] == "ASSIGNED"
    assert workflow_state_code(db_session, partial["id"]) == "PARTIALLY_ASSIGNED"
    assert workflow_state_code(db_session, full["id"]) == "ASSIGNED"


def test_request_status_transitions_create_workflow_executions_and_preserve_api_shape(client: TestClient, db_session: Session) -> None:
    refs = seed_refs(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], refs["facility"])  # type: ignore[arg-type]
    request = create_request(client, refs, [refs["cctv"]])  # type: ignore[list-item]
    before_keys = set(request)

    progress = client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "IN_PROGRESS"})
    complete = client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "COMPLETED"})
    close = client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "CLOSED"})

    assert progress.status_code == 200
    assert complete.status_code == 200
    assert close.status_code == 200
    assert set(close.json()) == before_keys
    assert workflow_state_code(db_session, request["id"]) == "CLOSED"
    instance = workflow_instance(db_session, request["id"])
    assert db_session.scalar(select(func.count(WorkflowTransitionExecution.id)).where(WorkflowTransitionExecution.workflow_instance_id == instance.id)) == 4
    request_uuid = UUID(request["id"])
    assert db_session.scalar(select(func.count(DomainEventOutbox.id)).where(DomainEventOutbox.aggregate_id == request_uuid, DomainEventOutbox.event_type == "WORKFLOW_TRANSITION_EXECUTED")) == 4
    assert db_session.scalar(select(func.count(RequestHistory.id)).where(RequestHistory.request_id == request_uuid)) >= 4


def test_reopen_and_cancel_synchronize(client: TestClient, db_session: Session) -> None:
    refs = seed_refs(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], refs["facility"])  # type: ignore[arg-type]
    request = create_request(client, refs, [refs["cctv"]])  # type: ignore[list-item]
    client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "IN_PROGRESS"})
    client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "COMPLETED"})
    reopen = client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "IN_PROGRESS"})
    cancel = client.post(f"/api/v1/requests/{request['id']}/status", json={"status": "CANCELLED"})

    assert reopen.status_code == 200
    assert cancel.status_code == 200
    assert workflow_state_code(db_session, request["id"]) == "CANCELLED"


def test_contractor_completion_rule_regression_and_assignment_sync(client: TestClient, db_session: Session, storage_root: str) -> None:
    refs = seed_refs(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], refs["facility"])  # type: ignore[arg-type]
    request = create_request(client, refs, [refs["cctv"]])  # type: ignore[list-item]
    assignment_id = request["assignments"][0]["id"]
    headers = {"X-Contractor-Id": str(refs["contractor_a"].id)}  # type: ignore[union-attr]
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "ACCEPTED"}, headers=headers)
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)

    rejected = client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "COMPLETED"}, headers=headers)
    upload = client.post(
        f"/api/v1/contractor/requests/{request['id']}/attachments",
        data={"category": "WORK_RESULT", "visibility": "SHARED", "assignment_id": assignment_id},
        files={"file": ("result.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    completed = client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "COMPLETED"}, headers=headers)

    assert rejected.status_code == 409
    assert upload.status_code == 201
    assert completed.status_code == 200
    assert workflow_state_code(db_session, request["id"]) == "COMPLETED"


def test_generic_read_api_respects_internal_and_contractor_scope(client: TestClient, db_session: Session) -> None:
    refs = seed_refs(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], refs["facility"])  # type: ignore[arg-type]
    request = create_request(client, refs, [refs["cctv"]])  # type: ignore[list-item]
    contractor_user = create_user_with_role(db_session, "CONTRACTOR_USER", refs["contractor_a"])  # type: ignore[arg-type]
    foreign_user = create_user_with_role(db_session, "CONTRACTOR_USER", refs["contractor_b"])  # type: ignore[arg-type]

    internal = client.get(f"/api/v1/workflows/instances/CONTRACTOR_REQUEST/{request['id']}")
    own = client.get(f"/api/v1/workflows/instances/CONTRACTOR_REQUEST/{request['id']}", headers={"X-User-Id": str(contractor_user.id)})
    foreign = client.get(f"/api/v1/workflows/instances/CONTRACTOR_REQUEST/{request['id']}", headers={"X-User-Id": str(foreign_user.id)})
    mutation = client.post(f"/api/v1/workflows/instances/CONTRACTOR_REQUEST/{request['id']}/transitions/START_WORK")

    assert internal.status_code == 200
    assert own.status_code == 200
    assert foreign.status_code == 404
    assert mutation.status_code in {401, 403, 409}
    assert "workflow_definition_id" in internal.json()
    assert "history" not in internal.json()
