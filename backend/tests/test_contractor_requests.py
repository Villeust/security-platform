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
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType


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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_reference_data(db: Session) -> dict[str, object]:
    city = City(name=f"City {uuid4()}", code=f"CITY-{uuid4()}")
    facility = Facility(city=city, name="HQ", address="Main street", code=f"FAC-{uuid4()}")
    premise = Premise(
        facility=facility,
        name="Server room",
        owner_name="Room Owner",
        owner_email="owner@example.com",
        owner_phone="+70000000000",
        has_access_control=True,
    )
    contractor_a = Contractor(name="Contractor A", code=f"CON-A-{uuid4()}")
    contractor_b = Contractor(name="Contractor B", code=f"CON-B-{uuid4()}")
    access_control = WorkType(name="СКУД", code=f"ACCESS_CONTROL-{uuid4()}", requires_premise=True)
    cctv = WorkType(name="СВН", code=f"CCTV-{uuid4()}", requires_premise=False)
    db.add_all([city, facility, premise, contractor_a, contractor_b, access_control, cctv])
    db.commit()
    for item in (city, facility, premise, contractor_a, contractor_b, access_control, cctv):
        db.refresh(item)
    return {
        "city": city,
        "facility": facility,
        "premise": premise,
        "contractor_a": contractor_a,
        "contractor_b": contractor_b,
        "access_control": access_control,
        "cctv": cctv,
    }


def add_responsibility(
    db: Session,
    contractor: Contractor,
    work_type: WorkType,
    facility: Facility | None = None,
    city: City | None = None,
    priority: int = 100,
) -> ContractorResponsibility:
    responsibility = ContractorResponsibility(
        contractor_id=contractor.id,
        city_id=city.id if city is not None else None,
        facility_id=facility.id if facility is not None else None,
        work_type_id=work_type.id,
        priority=priority,
    )
    db.add(responsibility)
    db.commit()
    db.refresh(responsibility)
    return responsibility


def request_payload(
    refs: dict[str, object],
    work_type_ids: list[str],
    premise: bool = True,
) -> dict[str, object]:
    facility = refs["facility"]
    city = refs["city"]
    premise_obj = refs["premise"]
    assert isinstance(city, City)
    assert isinstance(facility, Facility)
    assert isinstance(premise_obj, Premise)
    payload: dict[str, object] = {
        "city_id": str(city.id),
        "facility_id": str(facility.id),
        "title": "Install security equipment",
        "work_type_ids": work_type_ids,
    }
    if premise:
        payload["premise_id"] = str(premise_obj.id)
    return payload


def create_request(client: TestClient, refs: dict[str, object], work_types: list[WorkType], premise: bool = True) -> dict:
    response = client.post(
        "/api/v1/requests",
        json=request_payload(refs, [str(work_type.id) for work_type in work_types], premise=premise),
    )
    assert response.status_code == 201
    return response.json()


def test_access_control_request_requires_and_uses_premise(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access_control"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["access_control"]])  # type: ignore[list-item]

    assert created["status"] == "ASSIGNED"
    assert created["contact_name"] == "Room Owner"
    assert len(created["assignments"]) == 1


def test_cctv_request_does_not_require_premise(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    assert created["status"] == "ASSIGNED"
    assert created["premise_id"] is None


def test_mixed_access_control_and_cctv_request(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access_control"], facility=refs["facility"])  # type: ignore[arg-type]
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["access_control"], refs["cctv"]])  # type: ignore[list-item]

    assert created["status"] == "ASSIGNED"
    assert len(created["work_type_ids"]) == 2
    assert len(created["assignments"]) == 2


def test_premise_required_for_mixed_request(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)

    response = client.post(
        "/api/v1/requests",
        json=request_payload(
            refs,
            [str(refs["access_control"].id), str(refs["cctv"].id)],  # type: ignore[union-attr]
            premise=False,
        ),
    )

    assert response.status_code == 422


def test_one_contractor_assigned_to_both_work_types(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access_control"], facility=refs["facility"])  # type: ignore[arg-type]
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["access_control"], refs["cctv"]])  # type: ignore[list-item]

    contractor_ids = {assignment["contractor_id"] for assignment in created["assignments"]}
    assert contractor_ids == {str(refs["contractor_a"].id)}  # type: ignore[union-attr]


def test_different_contractors_assigned_to_different_work_types(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access_control"], facility=refs["facility"])  # type: ignore[arg-type]
    add_responsibility(db_session, refs["contractor_b"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["access_control"], refs["cctv"]])  # type: ignore[list-item]

    contractor_ids = {assignment["contractor_id"] for assignment in created["assignments"]}
    assert contractor_ids == {str(refs["contractor_a"].id), str(refs["contractor_b"].id)}  # type: ignore[union-attr]


def test_contractor_sees_own_company_request(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert len(response.json()["assignments"]) == 1


def test_contractor_does_not_see_foreign_request_in_list(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_b"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    response = client.get(
        "/api/v1/contractor/requests",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 200
    assert response.json() == []


def test_contractor_gets_404_for_foreign_request(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_b"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 404


def test_query_or_body_contractor_id_does_not_grant_foreign_access(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_b"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    assignment_id = created["assignments"][0]["id"]

    list_response = client.get(
        "/api/v1/contractor/requests",
        params={"contractor_id": str(refs["contractor_b"].id)},  # type: ignore[union-attr]
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )
    status_response = client.post(
        f"/api/v1/contractor/assignments/{assignment_id}/status",
        json={"contractor_id": str(refs["contractor_b"].id), "status": "ACCEPTED"},  # type: ignore[union-attr]
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert status_response.status_code == 404
