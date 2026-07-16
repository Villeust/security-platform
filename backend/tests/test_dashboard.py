from collections.abc import Generator
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AuthSource, Role, User, UserRole, UserType
from app.models.reference_data import City, Contractor, Facility, WorkType, utc_now
from app.models.requests import AssignmentStatus, ContractorRequest, RequestAssignment, RequestStatus, RequestWorkType
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
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def user_with_role(db: Session, role_code: str) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    user = User(
        username=f"{role_code.lower()}-{uuid4()}",
        display_name=role.name,
        user_type=UserType.CONTRACTOR if role_code.startswith("CONTRACTOR") else UserType.INTERNAL,
        auth_source=AuthSource.LOCAL,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def seed_dashboard_data(db: Session) -> None:
    city = City(name=f"City {uuid4()}", code=f"CITY-{uuid4()}")
    facility = Facility(city=city, name="Main Facility", address="Address", code=f"FAC-{uuid4()}")
    contractor = Contractor(name="Security Contractor", code=f"CON-{uuid4()}")
    work_type = WorkType(name="CCTV", code=f"CCTV-{uuid4()}", requires_premise=False)
    db.add_all([city, facility, contractor, work_type])
    db.flush()
    now = utc_now()
    overdue = ContractorRequest(
        request_number=f"CR-{uuid4()}",
        city_id=city.id,
        facility_id=facility.id,
        title="Overdue request",
        status=RequestStatus.IN_PROGRESS,
        desired_completion_date=now - timedelta(days=2),
    )
    new = ContractorRequest(
        request_number=f"CR-{uuid4()}",
        city_id=city.id,
        facility_id=facility.id,
        title="New request",
        status=RequestStatus.NEW,
        desired_completion_date=now + timedelta(days=2),
    )
    done = ContractorRequest(
        request_number=f"CR-{uuid4()}",
        city_id=city.id,
        facility_id=facility.id,
        title="Done request",
        status=RequestStatus.COMPLETED,
        completed_at=now - timedelta(days=1),
    )
    db.add_all([overdue, new, done])
    db.flush()
    for request in (overdue, new, done):
        db.add(RequestWorkType(request_id=request.id, work_type_id=work_type.id))
    db.add(RequestAssignment(request_id=overdue.id, contractor_id=contractor.id, work_type_id=work_type.id, status=AssignmentStatus.IN_PROGRESS))
    db.add(RequestAssignment(request_id=new.id, contractor_id=contractor.id, work_type_id=work_type.id, status=AssignmentStatus.ASSIGNED))
    db.add(RequestAssignment(request_id=done.id, contractor_id=contractor.id, work_type_id=work_type.id, status=AssignmentStatus.COMPLETED, completed_at=now - timedelta(days=1)))
    db.commit()


def test_dashboard_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard").status_code == 401


def test_contractor_user_cannot_access_dashboard(client: TestClient, db_session: Session) -> None:
    user = user_with_role(db_session, "CONTRACTOR_USER")
    assert client.get("/api/v1/dashboard", headers=auth(user)).status_code == 403


def test_internal_user_gets_safe_dashboard(client: TestClient, db_session: Session) -> None:
    seed_dashboard_data(db_session)
    user = user_with_role(db_session, "SECURITY_OPERATOR")
    response = client.get("/api/v1/dashboard", headers=auth(user), params={"period": "7d", "recent_limit": 3})
    assert response.status_code == 200
    payload = response.json()
    metrics = {item["key"]: item["value"] for item in payload["metrics"]}
    assert metrics["active_requests"] == 2
    assert metrics["new_requests"] == 1
    assert metrics["overdue_requests"] == 1
    assert metrics["completed_period"] == 1
    assert len(payload["request_groups"]["overdue"]) == 1
    assert len(payload["recent_activity"]) <= 3
    serialized = str(payload).lower()
    assert "password" not in serialized
    assert "token" not in serialized
    assert "session" not in serialized


def test_viewer_can_read_dashboard(client: TestClient, db_session: Session) -> None:
    user = user_with_role(db_session, "VIEWER")
    response = client.get("/api/v1/dashboard", headers=auth(user))
    assert response.status_code == 200
