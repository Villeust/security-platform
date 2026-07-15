from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType
from app.models.requests import ContractorRequest
from app.schemas.requests import ContractorRequestCreate
from app.services.request_service import create_contractor_request


DEMO_CITY_CODE = "DEMO-ALA"
DEMO_FACILITY_CODE = "DEMO-BC-STATUS"
DEMO_CONTRACTOR_ACCESS_CODE = "DEMO-SECURITY-ACCESS"
DEMO_CONTRACTOR_CCTV_CODE = "DEMO-SECURITY-CCTV"
DEMO_REQUEST_NUMBERS = {
    "ACCESS_ONLY": "DEMO-REQ-ACCESS-ONLY",
    "CCTV_ONLY": "DEMO-REQ-CCTV-ONLY",
    "BOTH_ONE": "DEMO-REQ-BOTH-ONE-CONTRACTOR",
    "BOTH_SPLIT": "DEMO-REQ-BOTH-SPLIT-CONTRACTORS",
}


@dataclass(frozen=True)
class SeedResult:
    contractors: dict[str, UUID]
    requests: list[ContractorRequest]


def get_or_create_city(db: Session) -> City:
    city = db.scalar(select(City).where(City.code == DEMO_CITY_CODE))
    if city is None:
        city = City(name="Алматы", code=DEMO_CITY_CODE)
        db.add(city)
        db.flush()
    return city


def get_or_create_facility(db: Session, city: City) -> Facility:
    facility = db.scalar(select(Facility).where(Facility.code == DEMO_FACILITY_CODE))
    if facility is None:
        facility = Facility(city_id=city.id, name="БЦ Статус", address="Алматы, демо-адрес", code=DEMO_FACILITY_CODE)
        db.add(facility)
        db.flush()
    return facility


def get_or_create_premise(db: Session, facility: Facility) -> Premise:
    premise = db.scalar(select(Premise).where(Premise.facility_id == facility.id, Premise.name == "Склад"))
    if premise is None:
        premise = Premise(
            facility_id=facility.id,
            name="Склад",
            number="DEMO-WH",
            category="warehouse",
            owner_name="Demo Premise Owner",
            owner_email="premise.owner@example.test",
            owner_phone="+70000000000",
            has_access_control=True,
        )
        db.add(premise)
        db.flush()
    return premise


def get_or_create_contractor(db: Session, name: str, code: str) -> Contractor:
    contractor = db.scalar(select(Contractor).where(Contractor.code == code))
    if contractor is None:
        contractor = Contractor(name=name, code=code, email=f"{code.lower()}@example.test", phone="+70000000001")
        db.add(contractor)
        db.flush()
    return contractor


def get_or_create_work_type(db: Session, name: str, code: str, requires_premise: bool) -> WorkType:
    work_type = db.scalar(select(WorkType).where(WorkType.code == code))
    if work_type is None:
        work_type = WorkType(name=name, code=code, requires_premise=requires_premise)
        db.add(work_type)
        db.flush()
    return work_type


def set_demo_responsibility(
    db: Session,
    contractor: Contractor,
    facility: Facility,
    work_type: WorkType,
    priority: int,
    is_active: bool = True,
) -> ContractorResponsibility:
    responsibility = db.scalar(
        select(ContractorResponsibility).where(
            ContractorResponsibility.contractor_id == contractor.id,
            ContractorResponsibility.facility_id == facility.id,
            ContractorResponsibility.work_type_id == work_type.id,
        )
    )
    if responsibility is None:
        responsibility = ContractorResponsibility(
            contractor_id=contractor.id,
            facility_id=facility.id,
            work_type_id=work_type.id,
        )
        db.add(responsibility)
    responsibility.city_id = None
    responsibility.priority = priority
    responsibility.is_active = is_active
    db.flush()
    return responsibility


def get_demo_request(db: Session, request_number: str) -> ContractorRequest | None:
    return db.scalar(
        select(ContractorRequest)
        .where(ContractorRequest.request_number == request_number)
        .options(selectinload(ContractorRequest.work_types), selectinload(ContractorRequest.assignments))
    )


def create_demo_request(
    db: Session,
    request_number: str,
    title: str,
    city: City,
    facility: Facility,
    premise: Premise | None,
    work_types: list[WorkType],
) -> ContractorRequest:
    existing = get_demo_request(db, request_number)
    if existing is not None:
        return existing

    payload = ContractorRequestCreate(
        city_id=city.id,
        facility_id=facility.id,
        premise_id=premise.id if premise is not None else None,
        title=title,
        description="Demo request created by explicit local seed command.",
        work_type_ids=[work_type.id for work_type in work_types],
    )
    request, _ = create_contractor_request(db, payload, request_number=request_number, commit=False)
    db.flush()
    return request


def run_seed(db: Session | None = None) -> SeedResult:
    if settings.environment.lower() in {"production", "prod"}:
        raise RuntimeError("Demo seed is blocked in production environment")

    owns_session = db is None
    session = db or SessionLocal()
    try:
        city = get_or_create_city(session)
        facility = get_or_create_facility(session, city)
        premise = get_or_create_premise(session, facility)
        contractor_access = get_or_create_contractor(session, "Demo Access Contractor", DEMO_CONTRACTOR_ACCESS_CODE)
        contractor_cctv = get_or_create_contractor(session, "Demo CCTV Contractor", DEMO_CONTRACTOR_CCTV_CODE)
        access_control = get_or_create_work_type(session, "СКУД", "ACCESS_CONTROL", True)
        cctv = get_or_create_work_type(session, "СВН", "CCTV", False)

        set_demo_responsibility(session, contractor_access, facility, access_control, priority=10, is_active=True)
        set_demo_responsibility(session, contractor_access, facility, cctv, priority=10, is_active=True)
        set_demo_responsibility(session, contractor_cctv, facility, cctv, priority=20, is_active=True)

        requests = [
            create_demo_request(
                session,
                DEMO_REQUEST_NUMBERS["ACCESS_ONLY"],
                "Demo: только ACCESS_CONTROL",
                city,
                facility,
                premise,
                [access_control],
            ),
            create_demo_request(
                session,
                DEMO_REQUEST_NUMBERS["CCTV_ONLY"],
                "Demo: только CCTV",
                city,
                facility,
                None,
                [cctv],
            ),
            create_demo_request(
                session,
                DEMO_REQUEST_NUMBERS["BOTH_ONE"],
                "Demo: ACCESS_CONTROL + CCTV одному подрядчику",
                city,
                facility,
                premise,
                [access_control, cctv],
            ),
        ]

        set_demo_responsibility(session, contractor_cctv, facility, cctv, priority=5, is_active=True)
        requests.append(
            create_demo_request(
                session,
                DEMO_REQUEST_NUMBERS["BOTH_SPLIT"],
                "Demo: ACCESS_CONTROL + CCTV разным подрядчикам",
                city,
                facility,
                premise,
                [access_control, cctv],
            )
        )

        if owns_session:
            session.commit()
        for request in requests:
            session.refresh(request)
        seeded_requests = [
            request
            for request in (get_demo_request(session, request.request_number or "") for request in requests)
            if request is not None
        ]
        return SeedResult(
            contractors={
                "access_contractor_id": contractor_access.id,
                "cctv_contractor_id": contractor_cctv.id,
            },
            requests=seeded_requests,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def print_result(result: SeedResult) -> None:
    print("Demo contractors:")
    for label, contractor_id in result.contractors.items():
        print(f"- {label}: {contractor_id}")

    print("\nDemo requests:")
    for request in result.requests:
        if request is None:
            continue
        print(f"- {request.request_number}: {request.id}")
        print(f"  work_type_ids: {', '.join(str(item.work_type_id) for item in request.work_types)}")
        for assignment in request.assignments:
            print(f"  assignment: work_type={assignment.work_type_id} contractor={assignment.contractor_id}")

    print("\nContractor API checks:")
    for contractor_id in result.contractors.values():
        print(f"curl -H \"X-Contractor-Id: {contractor_id}\" http://localhost:8000/api/v1/contractor/requests")


def main() -> None:
    result = run_seed()
    print_result(result)


if __name__ == "__main__":
    main()
