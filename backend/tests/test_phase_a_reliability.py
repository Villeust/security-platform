from __future__ import annotations

import json
import logging
from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.correlation import clear_correlation_id, set_correlation_id
from app.core.errors import AppErrorCode
from app.core.logging import JsonFormatter, redact
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AdminAuditLog, AuthSource, User, UserType
from app.models.workflow import DomainEventOutbox, WorkflowTransitionExecution
from app.services.contractor_request_workflow import register_contractor_request_workflow_adapter
from app.services.rbac_service import seed_rbac


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("create table alembic_version (version_num varchar(32) not null)"))
        connection.execute(text("insert into alembic_version (version_num) values ('20260717_0011')"))
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as session:
        seed_rbac(session)
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_correlation_id_generated_and_returned(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert UUID(response.headers["X-Correlation-ID"])


def test_valid_client_correlation_id_is_preserved(client: TestClient) -> None:
    correlation_id = str(uuid4())

    response = client.get("/api/v1/health", headers={"X-Correlation-ID": correlation_id})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_invalid_correlation_id_is_replaced_safely(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": "bad\r\nheader"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] != "bad\r\nheader"
    assert UUID(response.headers["X-Correlation-ID"])


def test_standard_error_response_includes_correlation_timestamp_and_path(client: TestClient) -> None:
    correlation_id = str(uuid4())

    response = client.get("/api/v1/admin/me", headers={"X-Correlation-ID": correlation_id})
    payload = response.json()

    assert response.status_code == 401
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert payload["correlation_id"] == correlation_id
    assert payload["path"] == "/api/v1/admin/me"
    assert payload["timestamp"]
    assert payload["error"]["code"] == AppErrorCode.AUTHENTICATION_REQUIRED.value
    assert payload["detail"] in {"Authentication is required", "User context is required"}


def test_validation_error_uses_standard_model(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={})
    payload = response.json()

    assert response.status_code == 422
    assert payload["error"]["code"] == AppErrorCode.VALIDATION_ERROR.value
    assert payload["detail"]
    assert payload["path"] == "/api/v1/auth/login"


def test_structured_logging_redacts_secrets() -> None:
    assert redact({"password": "secret", "nested": {"csrf_token": "abc"}, "safe": "ok"}) == {
        "password": "***",
        "nested": {"csrf_token": "***"},
        "safe": "ok",
    }
    set_correlation_id(str(uuid4()))
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
    output = json.loads(JsonFormatter().format(record))
    assert output["correlation_id"]
    assert output["message"] == "hello"
    clear_correlation_id()


def test_readiness_success(client: TestClient, db_session: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    register_contractor_request_workflow_adapter()
    monkeypatch.setattr("app.core.readiness._alembic_head", lambda: "20260717_0011")
    monkeypatch.setattr("app.core.readiness._backend_path", lambda: tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["database"] == "ok"
    assert response.json()["checks"]["platform_version"] == "ok"


def test_readiness_migration_mismatch_returns_503(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.readiness._alembic_head", lambda: "different")
    monkeypatch.setattr("app.core.readiness._backend_path", lambda: tmp_path)
    (tmp_path / "storage").mkdir()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["alembic_revision"] == "error"


def test_db_dependency_rolls_back_after_failure() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    router = APIRouter()

    @router.post("/__phase_a_failure")
    def fail_after_insert(db: Session = Depends(get_db)) -> None:
        db.add(User(username="rollback-test", display_name="Rollback", user_type=UserType.INTERNAL, auth_source=AuthSource.LOCAL))
        db.flush()
        raise RuntimeError("boom")

    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post("/__phase_a_failure")
        assert response.status_code == 500
        assert session.query(User).filter_by(username="rollback-test").count() == 0
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_audit_uses_request_correlation(client: TestClient, db_session: Session) -> None:
    correlation_id = str(uuid4())

    response = client.post(
        "/api/v1/admin/contractors",
        headers={"X-User-Role": "PLATFORM_ADMIN", "X-Correlation-ID": correlation_id},
        json={"name": "Correlation Contractor", "code": f"CID-{uuid4()}", "is_active": True},
    )

    assert response.status_code == 201
    audit = db_session.query(AdminAuditLog).filter_by(action="CONTRACTOR_CREATED").one()
    assert audit.correlation_id == correlation_id


def test_workflow_and_outbox_store_correlation(db_session: Session) -> None:
    from tests.test_workflow_engine import TEST_ENTITY_TYPE, DummyWorkflowAdapter, actor, create_definition
    from app.services.workflow_adapters import WorkflowActor
    from app.services.workflow_adapters import workflow_adapters
    from app.services.workflow_engine import execute_transition, start_workflow

    correlation_id = str(uuid4())
    set_correlation_id(correlation_id)
    try:
        workflow_adapters.clear()
        adapter = DummyWorkflowAdapter()
        workflow_adapters.register(adapter)
        current_actor = actor(db_session)
        assert current_actor.user is not None
        definition, parts = create_definition(db_session)
        entity_id = uuid4()
        adapter.entities.add(entity_id)
        instance = start_workflow(db_session, TEST_ENTITY_TYPE, entity_id, current_actor, workflow_code=definition.code)
        transition = parts["start"]
        execution = execute_transition(
            db_session,
            TEST_ENTITY_TYPE,
            entity_id,
            transition.code,
            WorkflowActor(user=current_actor.user, permissions={"workflows.instances.transition"}, actor_type="INTERNAL_USER"),
            workflow_code=definition.code,
        )
        db_session.flush()
        db_session.refresh(execution)
        assert db_session.get(WorkflowTransitionExecution, execution.id).correlation_id == correlation_id
        assert db_session.query(DomainEventOutbox).filter_by(correlation_id=correlation_id).count() >= 1
    finally:
        workflow_adapters.clear()
        register_contractor_request_workflow_adapter()
        clear_correlation_id()
