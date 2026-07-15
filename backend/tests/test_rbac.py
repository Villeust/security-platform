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
from app.models.admin import AdminAuditLog, AuthSource, ContractorMembership, Permission, Role, RolePermission, User, UserRole, UserType
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType
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


def user_with_role(db: Session, role_code: str, *, active: bool = True, locked: bool = False, contractors: list[Contractor] | None = None) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    user = User(
        username=f"{role_code.lower()}-{uuid4()}",
        display_name=role.name,
        email=None,
        user_type=UserType.CONTRACTOR if role_code.startswith("CONTRACTOR") else UserType.INTERNAL,
        auth_source=AuthSource.LOCAL,
        is_active=active,
        is_locked=locked,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    for index, contractor in enumerate(contractors or []):
        db.add(ContractorMembership(user_id=user.id, contractor_id=contractor.id, is_primary=index == 0, is_active=True))
    db.commit()
    db.refresh(user)
    return user


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def refs(db: Session) -> dict[str, object]:
    city = City(name=f"City {uuid4()}", code=f"CITY-{uuid4()}")
    facility = Facility(city=city, name="Facility", address="Address", code=f"FAC-{uuid4()}")
    premise = Premise(facility=facility, name="Premise")
    contractor_a = Contractor(name="Contractor A", code=f"A-{uuid4()}")
    contractor_b = Contractor(name="Contractor B", code=f"B-{uuid4()}")
    work_type = WorkType(name="CCTV", code=f"CCTV-{uuid4()}", requires_premise=False)
    db.add_all([city, facility, premise, contractor_a, contractor_b, work_type])
    db.commit()
    for item in (city, facility, premise, contractor_a, contractor_b, work_type):
        db.refresh(item)
    return {"city": city, "facility": facility, "premise": premise, "contractor_a": contractor_a, "contractor_b": contractor_b, "work_type": work_type}


def assigned_request(db: Session, contractor: Contractor, work_type: WorkType, city: City, facility: Facility) -> ContractorRequest:
    request = ContractorRequest(
        request_number=f"RBAC-{uuid4()}",
        city_id=city.id,
        facility_id=facility.id,
        title="RBAC request",
        description="RBAC",
        status=RequestStatus.ASSIGNED,
    )
    db.add(request)
    db.flush()
    db.add(RequestWorkType(request_id=request.id, work_type_id=work_type.id))
    db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id, work_type_id=work_type.id, status=AssignmentStatus.ASSIGNED))
    db.commit()
    db.refresh(request)
    return request


def test_request_without_user_context_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/requests")
    assert response.status_code == 401


def test_inactive_and_locked_users_return_403(client: TestClient, db_session: Session) -> None:
    inactive = user_with_role(db_session, "PLATFORM_ADMIN", active=False)
    locked = user_with_role(db_session, "PLATFORM_ADMIN", locked=True)
    assert client.get("/api/v1/admin/dashboard", headers=auth(inactive)).status_code == 403
    assert client.get("/api/v1/admin/dashboard", headers=auth(locked)).status_code == 403


def test_platform_admin_has_full_access(client: TestClient, db_session: Session) -> None:
    admin = user_with_role(db_session, "PLATFORM_ADMIN")
    assert client.get("/api/v1/admin/dashboard", headers=auth(admin)).status_code == 200
    assert client.get("/api/v1/admin/users", headers=auth(admin)).status_code == 200


def test_security_operator_cannot_manage_users(client: TestClient, db_session: Session) -> None:
    operator = user_with_role(db_session, "SECURITY_OPERATOR")
    response = client.post("/api/v1/admin/users", headers=auth(operator), json={"username": "op", "display_name": "Op", "user_type": "INTERNAL"})
    assert response.status_code == 403


def test_viewer_reads_requests_but_cannot_create(client: TestClient, db_session: Session) -> None:
    viewer = user_with_role(db_session, "VIEWER")
    assert client.get("/api/v1/requests", headers=auth(viewer)).status_code == 200
    response = client.post("/api/v1/requests", headers=auth(viewer), json={"title": "No", "description": "No", "work_type_ids": []})
    assert response.status_code == 403


def test_contractor_user_cannot_access_admin(client: TestClient, db_session: Session) -> None:
    contractor = refs(db_session)["contractor_a"]
    assert isinstance(contractor, Contractor)
    user = user_with_role(db_session, "CONTRACTOR_USER", contractors=[contractor])
    assert client.get("/api/v1/admin/dashboard", headers=auth(user)).status_code == 403


def test_contractor_tenant_isolation_and_multiple_memberships(client: TestClient, db_session: Session) -> None:
    data = refs(db_session)
    contractor_a = data["contractor_a"]
    contractor_b = data["contractor_b"]
    work_type = data["work_type"]
    city = data["city"]
    facility = data["facility"]
    assert isinstance(contractor_a, Contractor) and isinstance(contractor_b, Contractor) and isinstance(work_type, WorkType)
    assert isinstance(city, City) and isinstance(facility, Facility)
    request_a = assigned_request(db_session, contractor_a, work_type, city, facility)
    request_b = assigned_request(db_session, contractor_b, work_type, city, facility)

    user_a = user_with_role(db_session, "CONTRACTOR_USER", contractors=[contractor_a])
    multi = user_with_role(db_session, "CONTRACTOR_MANAGER", contractors=[contractor_a, contractor_b])

    assert client.get(f"/api/v1/contractor/requests/{request_a.id}", headers=auth(user_a)).status_code == 200
    assert client.get(f"/api/v1/contractor/requests/{request_b.id}", headers=auth(user_a)).status_code == 404
    assert len(client.get("/api/v1/contractor/requests", headers=auth(multi)).json()) == 2

    assignment_b = db_session.scalar(select(RequestAssignment).where(RequestAssignment.request_id == request_b.id))
    assert assignment_b is not None
    assert client.post(f"/api/v1/contractor/assignments/{assignment_b.id}/status", headers=auth(user_a), json={"status": "ACCEPTED"}).status_code == 404


def test_dev_headers_are_forbidden_in_production(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    try:
        response = client.get("/api/v1/requests", headers={"X-User-Role": "PLATFORM_ADMIN"})
        assert response.status_code == 401
    finally:
        monkeypatch.setattr(settings, "environment", "development")


def test_role_permission_seed_is_idempotent(db_session: Session) -> None:
    seed_rbac(db_session)
    first_count = db_session.scalar(select(func.count(Permission.id)))
    seed_rbac(db_session)
    second_count = db_session.scalar(select(func.count(Permission.id)))
    assert first_count == second_count


def test_system_permission_has_no_delete_endpoint(client: TestClient, db_session: Session) -> None:
    admin = user_with_role(db_session, "PLATFORM_ADMIN")
    permission = db_session.scalar(select(Permission))
    assert permission is not None
    assert client.delete(f"/api/v1/admin/permissions/{permission.id}", headers=auth(admin)).status_code in {404, 405}


def test_role_permission_change_writes_audit(client: TestClient, db_session: Session) -> None:
    admin = user_with_role(db_session, "PLATFORM_ADMIN")
    role = db_session.scalar(select(Role).where(Role.code == "VIEWER"))
    permission = db_session.scalar(select(Permission).where(Permission.code == "requests.view"))
    assert role is not None and permission is not None
    response = client.put(f"/api/v1/admin/roles/{role.id}/permissions", headers=auth(admin), json={"permission_ids": [str(permission.id)]})
    assert response.status_code == 200
    assert db_session.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "ROLE_PERMISSIONS_CHANGED")) is not None


def test_x_contractor_id_does_not_bypass_x_user_id(client: TestClient, db_session: Session) -> None:
    data = refs(db_session)
    contractor_a = data["contractor_a"]
    contractor_b = data["contractor_b"]
    work_type = data["work_type"]
    city = data["city"]
    facility = data["facility"]
    assert isinstance(contractor_a, Contractor) and isinstance(contractor_b, Contractor) and isinstance(work_type, WorkType)
    assert isinstance(city, City) and isinstance(facility, Facility)
    request_b = assigned_request(db_session, contractor_b, work_type, city, facility)
    user_a = user_with_role(db_session, "CONTRACTOR_USER", contractors=[contractor_a])
    headers = {**auth(user_a), "X-Contractor-Id": str(contractor_b.id)}
    assert client.get(f"/api/v1/contractor/requests/{request_b.id}", headers=headers).status_code == 404
