from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.reference_data import City, Contractor, WorkType


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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


def create_city(client: TestClient, name: str = "Almaty", code: str = "ALA") -> dict:
    response = client.post("/api/v1/cities", json={"name": name, "code": code})
    assert response.status_code == 201
    return response.json()


def create_facility(client: TestClient, city_id: str, code: str = "FAC-1") -> dict:
    response = client.post(
        "/api/v1/facilities",
        json={
            "city_id": city_id,
            "name": "Main Office",
            "address": "1 Security Ave",
            "code": code,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_contractor(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/contractors",
        json={"name": "Secure Works", "code": "SECURE"},
    )
    assert response.status_code == 201
    return response.json()


def create_work_type(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/work-types",
        json={"name": "СКУД", "code": "ACCESS_CONTROL", "requires_premise": True},
    )
    assert response.status_code == 201
    return response.json()


def test_reference_model_defaults(db_session: Session) -> None:
    city = City(name="Astana", code="AST")
    contractor = Contractor(name="Security Partner", code="PARTNER")
    work_type = WorkType(name="СВН", code="CCTV")

    db_session.add_all([city, contractor, work_type])
    db_session.commit()
    db_session.refresh(city)

    assert city.id is not None
    assert city.is_active is True
    assert city.created_at is not None
    assert city.updated_at is not None
    assert work_type.requires_premise is False


def test_city_crud_filters_and_unique_conflict(client: TestClient) -> None:
    city = create_city(client)

    duplicate = client.post("/api/v1/cities", json={"name": "Almaty", "code": "ALA2"})
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/cities", params={"search": "ALA", "is_active": True})
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == city["id"]

    updated = client.patch(f"/api/v1/cities/{city['id']}", json={"is_active": False})
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/v1/cities/{city['id']}")
    assert deleted.status_code == 204


def test_facility_premise_filters_and_delete_restriction(client: TestClient) -> None:
    city = create_city(client)
    facility = create_facility(client, city["id"])

    premise_response = client.post(
        "/api/v1/premises",
        json={
            "facility_id": facility["id"],
            "name": "Server Room",
            "has_access_control": True,
        },
    )
    assert premise_response.status_code == 201

    facilities = client.get("/api/v1/facilities", params={"city_id": city["id"]})
    assert len(facilities.json()) == 1

    premises = client.get("/api/v1/premises", params={"facility_id": facility["id"]})
    assert premises.json()[0]["name"] == "Server Room"

    delete_facility = client.delete(f"/api/v1/facilities/{facility['id']}")
    assert delete_facility.status_code == 409


def test_contractor_responsibility_filters_and_fk_validation(client: TestClient) -> None:
    city = create_city(client)
    facility = create_facility(client, city["id"])
    contractor = create_contractor(client)
    work_type = create_work_type(client)

    response = client.post(
        "/api/v1/contractor-responsibilities",
        json={
            "contractor_id": contractor["id"],
            "city_id": city["id"],
            "facility_id": facility["id"],
            "work_type_id": work_type["id"],
            "priority": 10,
        },
    )
    assert response.status_code == 201

    listed = client.get(
        "/api/v1/contractor-responsibilities",
        params={"contractor_id": contractor["id"], "work_type_id": work_type["id"]},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["priority"] == 10

    delete_contractor = client.delete(f"/api/v1/contractors/{contractor['id']}")
    assert delete_contractor.status_code == 409

    invalid = client.post(
        "/api/v1/contractor-responsibilities",
        json={
            "contractor_id": "00000000-0000-0000-0000-000000000001",
            "work_type_id": work_type["id"],
        },
    )
    assert invalid.status_code == 404
