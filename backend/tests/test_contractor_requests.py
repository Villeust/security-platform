from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
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
        "description": "Install and configure equipment.",
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


@pytest.fixture()
def storage_root(tmp_path) -> str:  # type: ignore[no-untyped-def]
    original = settings.storage_root
    settings.storage_root = str(tmp_path)
    yield str(tmp_path)
    settings.storage_root = original


def upload_attachment(
    client: TestClient,
    request_id: str,
    filename: str = "result.pdf",
    content: bytes = b"%PDF-1.4 test",
    mime_type: str = "application/pdf",
    category: str = "REQUEST_FILE",
    visibility: str = "SHARED",
    assignment_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> object:
    data: dict[str, str] = {"category": category, "visibility": visibility}
    if assignment_id is not None:
        data["assignment_id"] = assignment_id
    response = client.post(
        f"/api/v1/requests/{request_id}/attachments" if headers is None else f"/api/v1/contractor/requests/{request_id}/attachments",
        data=data,
        files={"file": (filename, content, mime_type)},
        headers=headers,
    )
    return response


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


def create_draft(client: TestClient, payload: dict[str, object]) -> dict:
    response = client.post("/api/v1/requests", json={**payload, "save_as_draft": True})
    assert response.status_code == 201
    return response.json()


def test_create_draft(client: TestClient) -> None:
    created = create_draft(client, {"title": "Draft request", "description": "Draft description"})

    assert created["status"] == "DRAFT"
    assert created["request_number"]
    assert created["assignments"] == []


def test_draft_allows_incomplete_data(client: TestClient) -> None:
    created = create_draft(client, {"title": "Incomplete draft", "description": "Only the required draft fields"})

    assert created["city_id"] is None
    assert created["facility_id"] is None
    assert created["work_type_ids"] == []


def test_publish_full_request(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    draft = create_draft(client, request_payload(refs, [str(refs["cctv"].id)], premise=False))  # type: ignore[union-attr]

    response = client.post(f"/api/v1/requests/{draft['id']}/publish")

    assert response.status_code == 200
    assert response.json()["status"] == "ASSIGNED"
    assert len(response.json()["assignments"]) == 1


def test_publish_incomplete_request_returns_error(client: TestClient) -> None:
    draft = create_draft(client, {"title": "Incomplete", "description": "Missing scope"})

    response = client.post(f"/api/v1/requests/{draft['id']}/publish")

    assert response.status_code == 422


def test_repeat_publish_does_not_duplicate_assignments(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    draft = create_draft(client, request_payload(refs, [str(refs["cctv"].id)], premise=False))  # type: ignore[union-attr]

    first = client.post(f"/api/v1/requests/{draft['id']}/publish")
    second = client.post(f"/api/v1/requests/{draft['id']}/publish")

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(second.json()["assignments"]) == 1


def test_assigned_when_all_work_types_have_contractors(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access_control"], facility=refs["facility"])  # type: ignore[arg-type]
    add_responsibility(db_session, refs["contractor_b"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["access_control"], refs["cctv"]])  # type: ignore[list-item]

    assert created["status"] == "ASSIGNED"


def test_partially_assigned_when_only_some_work_types_have_contractors(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["access_control"], facility=refs["facility"])  # type: ignore[arg-type]

    created = create_request(client, refs, [refs["access_control"], refs["cctv"]])  # type: ignore[list-item]

    assert created["status"] == "PARTIALLY_ASSIGNED"
    assert created["unassigned_work_type_ids"] == [str(refs["cctv"].id)]  # type: ignore[union-attr]


def test_new_when_no_contractors_found(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)

    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    assert created["status"] == "NEW"
    assert created["assignments"] == []


def test_valid_status_transition(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "IN_PROGRESS"})

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_invalid_status_transition(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "CLOSED"})

    assert response.status_code == 409


def test_completed_sets_completed_at(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "IN_PROGRESS"})

    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "COMPLETED"})

    assert response.status_code == 200
    assert response.json()["completed_at"] is not None


def test_closed_sets_closed_at(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "IN_PROGRESS"})
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "COMPLETED"})

    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "CLOSED"})

    assert response.status_code == 200
    assert response.json()["closed_at"] is not None


def test_completed_can_return_to_in_progress(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "IN_PROGRESS"})
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "COMPLETED"})

    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "IN_PROGRESS"})

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["completed_at"] is None


def test_edit_draft(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    draft = create_draft(client, {"title": "Draft", "description": "Draft description"})

    response = client.patch(
        f"/api/v1/requests/{draft['id']}",
        json={
            "city_id": str(refs["city"].id),  # type: ignore[union-attr]
            "facility_id": str(refs["facility"].id),  # type: ignore[union-attr]
            "title": "Updated draft",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated draft"


def test_closed_request_cannot_be_edited(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "IN_PROGRESS"})
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "COMPLETED"})
    client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "CLOSED"})

    response = client.patch(f"/api/v1/requests/{created['id']}", json={"title": "Nope"})

    assert response.status_code == 409


def test_changed_fields_are_recorded(client: TestClient) -> None:
    draft = create_draft(client, {"title": "Old", "description": "Draft description"})

    response = client.patch(f"/api/v1/requests/{draft['id']}", json={"title": "New"})
    history = client.get(f"/api/v1/requests/{draft['id']}/history")

    assert response.status_code == 200
    updated = [item for item in history.json() if item["event_type"] == "UPDATED"]
    assert updated[-1]["changed_fields"]["title"] == {"old": "Old", "new": "New"}


def test_contractor_accepts_assignment(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    response = client.post(
        f"/api/v1/contractor/requests/{created['id']}/accept",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 200
    assert response.json()["assignments"][0]["status"] == "ACCEPTED"
    assert response.json()["status"] == "IN_PROGRESS"


def test_all_assignments_completed_sets_request_completed(client: TestClient, db_session: Session, storage_root: str) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    assignment_id = created["assignments"][0]["id"]
    headers = {"X-Contractor-Id": str(refs["contractor_a"].id)}  # type: ignore[union-attr]
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "ACCEPTED"}, headers=headers)
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)
    upload_attachment(client, created["id"], category="WORK_RESULT", assignment_id=assignment_id, headers=headers)

    response = client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "COMPLETED"}, headers=headers)
    request = client.get(f"/api/v1/requests/{created['id']}")

    assert response.status_code == 200
    assert request.json()["status"] == "COMPLETED"


def test_server_side_search(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    response = client.post(
        "/api/v1/requests",
        json={**request_payload(refs, [str(refs["cctv"].id)], premise=False), "title": "Unique Needle Request"},  # type: ignore[union-attr]
    )
    assert response.status_code == 201

    listed = client.get("/api/v1/requests", params={"search": "Needle"})

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [response.json()["id"]]


def test_server_side_filters(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]

    listed = client.get(
        "/api/v1/requests",
        params={
            "status": "ASSIGNED",
            "city_id": str(refs["city"].id),  # type: ignore[union-attr]
            "facility_id": str(refs["facility"].id),  # type: ignore[union-attr]
            "work_type_id": str(refs["cctv"].id),  # type: ignore[union-attr]
            "contractor_id": str(refs["contractor_a"].id),  # type: ignore[union-attr]
            "sort_by": "number",
            "sort_order": "asc",
        },
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]


def test_contractor_history_hides_internal_details(client: TestClient, db_session: Session) -> None:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    client.patch(f"/api/v1/requests/{created['id']}", json={"title": "Internal update"})
    client.post(
        f"/api/v1/contractor/requests/{created['id']}/accept",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}/history",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 200
    events = response.json()
    assert "UPDATED" not in {item["event_type"] for item in events}
    assert all(item["actor_id"] is None or item["actor_type"] == "CONTRACTOR_USER" for item in events)
    assert all(item["changed_fields"] is None or set(item["changed_fields"]) <= {"assignment_status"} for item in events)


def assigned_request(client: TestClient, db_session: Session) -> tuple[dict, dict[str, object]]:
    refs = seed_reference_data(db_session)
    add_responsibility(db_session, refs["contractor_a"], refs["cctv"], facility=refs["facility"])  # type: ignore[arg-type]
    created = create_request(client, refs, [refs["cctv"]], premise=False)  # type: ignore[list-item]
    return created, refs


def test_internal_creates_shared_comment(client: TestClient, db_session: Session) -> None:
    created, _ = assigned_request(client, db_session)

    response = client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Shared note", "visibility": "SHARED"})

    assert response.status_code == 201
    assert response.json()["visibility"] == "SHARED"


def test_internal_creates_internal_comment(client: TestClient, db_session: Session) -> None:
    created, _ = assigned_request(client, db_session)

    response = client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Internal note", "visibility": "INTERNAL"})

    assert response.status_code == 201
    assert response.json()["visibility"] == "INTERNAL"


def test_contractor_creates_shared_comment(client: TestClient, db_session: Session) -> None:
    created, refs = assigned_request(client, db_session)

    response = client.post(
        f"/api/v1/contractor/requests/{created['id']}/comments",
        json={"body": "Contractor note", "visibility": "SHARED"},
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 201
    assert response.json()["visibility"] == "SHARED"


def test_contractor_cannot_create_internal_comment(client: TestClient, db_session: Session) -> None:
    created, refs = assigned_request(client, db_session)

    response = client.post(
        f"/api/v1/contractor/requests/{created['id']}/comments",
        json={"body": "Hidden note", "visibility": "INTERNAL"},
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 403


def test_contractor_does_not_see_internal_comment(client: TestClient, db_session: Session) -> None:
    created, refs = assigned_request(client, db_session)
    client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Internal note", "visibility": "INTERNAL"})
    client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Shared note", "visibility": "SHARED"})

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}/comments",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 200
    assert [item["body"] for item in response.json()] == ["Shared note"]


def test_contractor_does_not_see_comments_for_foreign_request(client: TestClient, db_session: Session) -> None:
    created, refs = assigned_request(client, db_session)

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}/comments",
        headers={"X-Contractor-Id": str(refs["contractor_b"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 404


def test_edit_own_comment(client: TestClient, db_session: Session) -> None:
    created, _ = assigned_request(client, db_session)
    actor_id = str(uuid4())
    comment = client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Old", "visibility": "SHARED"}, headers={"X-Actor-Id": actor_id}).json()

    response = client.patch(f"/api/v1/requests/{created['id']}/comments/{comment['id']}", json={"body": "New"}, headers={"X-Actor-Id": actor_id})

    assert response.status_code == 200
    assert response.json()["body"] == "New"
    assert response.json()["is_edited"] is True


def test_cannot_edit_foreign_comment(client: TestClient, db_session: Session) -> None:
    created, _ = assigned_request(client, db_session)
    comment = client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Old", "visibility": "SHARED"}, headers={"X-Actor-Id": str(uuid4())}).json()

    response = client.patch(f"/api/v1/requests/{created['id']}/comments/{comment['id']}", json={"body": "New"}, headers={"X-Actor-Id": str(uuid4())})

    assert response.status_code == 403


def test_soft_delete_comment(client: TestClient, db_session: Session) -> None:
    created, _ = assigned_request(client, db_session)
    actor_id = str(uuid4())
    comment = client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Delete me", "visibility": "SHARED"}, headers={"X-Actor-Id": actor_id}).json()

    response = client.delete(f"/api/v1/requests/{created['id']}/comments/{comment['id']}", headers={"X-Actor-Id": actor_id})

    assert response.status_code == 200
    assert response.json()["is_deleted"] is True
    assert response.json()["body"] == "Комментарий удалён"


def test_upload_allowed_file(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)

    response = upload_attachment(client, created["id"], filename="photo.jpg", content=b"jpg", mime_type="image/jpeg", category="PHOTO")

    assert response.status_code == 201
    assert response.json()["original_filename"] == "photo.jpg"


def test_forbidden_extension_is_rejected(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)

    response = upload_attachment(client, created["id"], filename="run.exe", content=b"exe", mime_type="application/octet-stream")

    assert response.status_code == 415


def test_file_over_size_limit_is_rejected(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)

    response = upload_attachment(client, created["id"], filename="big.pdf", content=b"x" * (20 * 1024 * 1024 + 1), mime_type="application/pdf")

    assert response.status_code == 413


def test_checksum_is_created(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)

    response = upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain")

    assert response.status_code == 201
    assert len(response.json()["checksum_sha256"]) == 64


def test_download_accessible_file(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)
    uploaded = upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain").json()

    response = client.get(f"/api/v1/requests/{created['id']}/attachments/{uploaded['id']}/download")

    assert response.status_code == 200
    assert response.content == b"hello"


def test_contractor_cannot_download_internal_attachment(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, refs = assigned_request(client, db_session)
    uploaded = upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain", visibility="INTERNAL").json()

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}/attachments/{uploaded['id']}/download",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 404


def test_contractor_cannot_download_foreign_attachment(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, refs = assigned_request(client, db_session)
    uploaded = upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain").json()

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}/attachments/{uploaded['id']}/download",
        headers={"X-Contractor-Id": str(refs["contractor_b"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 404


def test_work_result_requires_assignment_id(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, refs = assigned_request(client, db_session)

    response = upload_attachment(
        client,
        created["id"],
        category="WORK_RESULT",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 422


def test_assignment_id_must_belong_to_contractor(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, refs = assigned_request(client, db_session)

    response = upload_attachment(
        client,
        created["id"],
        category="WORK_RESULT",
        assignment_id=created["assignments"][0]["id"],
        headers={"X-Contractor-Id": str(refs["contractor_b"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 404


def test_completion_without_work_result_is_rejected(client: TestClient, db_session: Session) -> None:
    created, refs = assigned_request(client, db_session)
    assignment_id = created["assignments"][0]["id"]
    headers = {"X-Contractor-Id": str(refs["contractor_a"].id)}  # type: ignore[union-attr]
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "ACCEPTED"}, headers=headers)
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)

    response = client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "COMPLETED"}, headers=headers)

    assert response.status_code == 409


def test_completion_with_work_result_is_allowed(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, refs = assigned_request(client, db_session)
    assignment_id = created["assignments"][0]["id"]
    headers = {"X-Contractor-Id": str(refs["contractor_a"].id)}  # type: ignore[union-attr]
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "ACCEPTED"}, headers=headers)
    client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "IN_PROGRESS"}, headers=headers)
    upload_attachment(client, created["id"], category="WORK_RESULT", assignment_id=assignment_id, headers=headers)

    response = client.post(f"/api/v1/contractor/assignments/{assignment_id}/status", json={"status": "COMPLETED"}, headers=headers)

    assert response.status_code == 200


def test_attachment_history_is_recorded(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)
    upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain")

    history = client.get(f"/api/v1/requests/{created['id']}/history").json()

    assert "ATTACHMENT_ADDED" in {item["event_type"] for item in history}


def test_contractor_safe_history_hides_internal_collaboration_events(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, refs = assigned_request(client, db_session)
    client.post(f"/api/v1/requests/{created['id']}/comments", json={"body": "Internal note", "visibility": "INTERNAL"})
    upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain", visibility="INTERNAL")

    response = client.get(
        f"/api/v1/contractor/requests/{created['id']}/history",
        headers={"X-Contractor-Id": str(refs["contractor_a"].id)},  # type: ignore[union-attr]
    )

    assert response.status_code == 200
    assert "COMMENT_ADDED" not in {item["event_type"] for item in response.json()}
    assert "ATTACHMENT_ADDED" not in {item["event_type"] for item in response.json()}


def test_path_traversal_filename_is_rejected(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)

    response = upload_attachment(client, created["id"], filename="../evil.pdf", content=b"evil", mime_type="application/pdf")

    assert response.status_code == 415


def test_deleted_attachment_is_not_listed(client: TestClient, db_session: Session, storage_root: str) -> None:
    created, _ = assigned_request(client, db_session)
    uploaded = upload_attachment(client, created["id"], filename="doc.txt", content=b"hello", mime_type="text/plain").json()

    delete_response = client.delete(f"/api/v1/requests/{created['id']}/attachments/{uploaded['id']}")
    listed = client.get(f"/api/v1/requests/{created['id']}/attachments")

    assert delete_response.status_code == 200
    assert listed.json() == []
