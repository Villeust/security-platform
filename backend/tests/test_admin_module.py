from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.reference_data import Contractor


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as session:
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


def create_admin_contractor(client: TestClient, code: str | None = None) -> dict:
    response = client.post(
        "/api/v1/admin/contractors",
        json={
            "name": f"Admin Contractor {uuid4()}",
            "code": code or f"ADM-{uuid4()}",
            "email": "contractor@example.test",
            "phone": "+70000000000",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def first_role(client: TestClient) -> dict:
    response = client.get("/api/v1/admin/roles")
    assert response.status_code == 200
    return response.json()[0]


def test_create_contractor(client: TestClient) -> None:
    created = create_admin_contractor(client)
    assert created["id"]
    assert created["is_active"] is True


def test_contractor_code_unique(client: TestClient) -> None:
    code = f"DUP-{uuid4()}"
    create_admin_contractor(client, code=code)
    response = client.post("/api/v1/admin/contractors", json={"name": "Duplicate", "code": code})
    assert response.status_code == 409


def test_deactivate_contractor(client: TestClient) -> None:
    created = create_admin_contractor(client)
    response = client.post(f"/api/v1/admin/contractors/{created['id']}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_create_internal_user(client: TestClient) -> None:
    role = first_role(client)
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": f"internal-{uuid4()}",
            "email": f"internal-{uuid4()}@example.test",
            "display_name": "Internal User",
            "user_type": "INTERNAL",
            "auth_source": "LOCAL",
            "role_ids": [role["id"]],
            "contractor_memberships": [],
        },
    )
    assert response.status_code == 201
    assert response.json()["role_ids"] == [role["id"]]


def test_create_contractor_user(client: TestClient) -> None:
    contractor = create_admin_contractor(client)
    role = first_role(client)
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": f"contractor-{uuid4()}",
            "email": f"contractor-{uuid4()}@example.test",
            "display_name": "Contractor User",
            "user_type": "CONTRACTOR",
            "auth_source": "LOCAL",
            "role_ids": [role["id"]],
            "contractor_memberships": [{"contractor_id": contractor["id"], "is_primary": True, "is_active": True}],
        },
    )
    assert response.status_code == 201
    assert response.json()["contractor_memberships"][0]["contractor_id"] == contractor["id"]


def test_contractor_user_without_membership_forbidden(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": f"contractor-no-membership-{uuid4()}",
            "display_name": "Contractor User",
            "user_type": "CONTRACTOR",
            "auth_source": "LOCAL",
            "role_ids": [],
            "contractor_memberships": [],
        },
    )
    assert response.status_code == 422


def test_username_unique(client: TestClient) -> None:
    username = f"user-{uuid4()}"
    payload = {"username": username, "display_name": "User", "user_type": "INTERNAL", "auth_source": "LOCAL"}
    assert client.post("/api/v1/admin/users", json=payload).status_code == 201
    assert client.post("/api/v1/admin/users", json=payload).status_code == 409


def test_email_unique(client: TestClient) -> None:
    email = f"user-{uuid4()}@example.test"
    assert client.post("/api/v1/admin/users", json={"username": f"u1-{uuid4()}", "email": email, "display_name": "User", "user_type": "INTERNAL", "auth_source": "LOCAL"}).status_code == 201
    assert client.post("/api/v1/admin/users", json={"username": f"u2-{uuid4()}", "email": email, "display_name": "User", "user_type": "INTERNAL", "auth_source": "LOCAL"}).status_code == 409


def test_assign_roles(client: TestClient) -> None:
    user = client.post("/api/v1/admin/users", json={"username": f"roles-{uuid4()}", "display_name": "Roles", "user_type": "INTERNAL", "auth_source": "LOCAL"}).json()
    role = first_role(client)
    response = client.put(f"/api/v1/admin/users/{user['id']}/roles", json={"role_ids": [role["id"]]})
    assert response.status_code == 200
    assert response.json()["role_ids"] == [role["id"]]


def test_assign_contractor_membership(client: TestClient) -> None:
    user = client.post("/api/v1/admin/users", json={"username": f"member-{uuid4()}", "display_name": "Member", "user_type": "CONTRACTOR", "auth_source": "LOCAL", "contractor_memberships": [{"contractor_id": create_admin_contractor(client)["id"]}]}).json()
    contractor = create_admin_contractor(client)
    response = client.put(f"/api/v1/admin/users/{user['id']}/contractors", json={"contractor_memberships": [{"contractor_id": contractor["id"], "is_primary": True}]})
    assert response.status_code == 200
    assert response.json()["contractor_memberships"][0]["contractor_id"] == contractor["id"]


def test_system_role_cannot_be_deactivated(client: TestClient) -> None:
    role = first_role(client)
    response = client.post(f"/api/v1/admin/roles/{role['id']}/deactivate")
    assert response.status_code == 409


def test_admin_action_writes_audit(client: TestClient) -> None:
    create_admin_contractor(client)
    response = client.get("/api/v1/admin/audit", params={"action": "CONTRACTOR_CREATED"})
    assert response.status_code == 200
    assert response.json()


def test_dashboard_counts(client: TestClient) -> None:
    create_admin_contractor(client)
    client.post("/api/v1/admin/users", json={"username": f"dash-{uuid4()}", "display_name": "Dash", "user_type": "INTERNAL", "auth_source": "LOCAL"})
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 200
    assert response.json()["contractors_total"] == 1
    assert response.json()["users_total"] == 2


def test_system_status(client: TestClient) -> None:
    response = client.get("/api/v1/admin/system-status")
    assert response.status_code == 200
    assert response.json()["backend"]["status"] == "operational"


def test_audit_filters(client: TestClient) -> None:
    create_admin_contractor(client)
    response = client.get("/api/v1/admin/audit", params={"entity_type": "Contractor", "action": "CONTRACTOR_CREATED"})
    assert response.status_code == 200
    assert {item["entity_type"] for item in response.json()} == {"Contractor"}


def test_inactive_records_are_filtered(client: TestClient, db_session: Session) -> None:
    active = create_admin_contractor(client)
    inactive = Contractor(name=f"Inactive {uuid4()}", code=f"INACTIVE-{uuid4()}", is_active=False)
    db_session.add(inactive)
    db_session.commit()
    response = client.get("/api/v1/admin/contractors", params={"is_active": True})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [active["id"]]
