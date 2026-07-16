from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.models.admin import User
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType
from app.models.requests import ContractorRequest
from app.scripts.seed_demo import (
    DEMO_CONTRACTOR_ACCESS_CODE,
    DEMO_CONTRACTOR_CCTV_CODE,
    DEMO_REQUEST_NUMBERS,
    run_seed,
)


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


def table_counts(db: Session) -> dict[str, int]:
    return {
        "cities": db.scalar(select(func.count()).select_from(City)),
        "facilities": db.scalar(select(func.count()).select_from(Facility)),
        "premises": db.scalar(select(func.count()).select_from(Premise)),
        "contractors": db.scalar(select(func.count()).select_from(Contractor)),
        "work_types": db.scalar(select(func.count()).select_from(WorkType)),
        "responsibilities": db.scalar(select(func.count()).select_from(ContractorResponsibility)),
        "requests": db.scalar(select(func.count()).select_from(ContractorRequest)),
    }


def test_seed_is_idempotent(db_session: Session) -> None:
    run_seed(db_session)
    first_counts = table_counts(db_session)

    run_seed(db_session)
    second_counts = table_counts(db_session)

    assert second_counts == first_counts
    assert second_counts["requests"] == 4


def test_seed_demo_users_password_state(db_session: Session) -> None:
    run_seed(db_session)

    platform_admin = db_session.scalar(select(User).where(User.username == "dev.platform.admin"))
    temp_user = db_session.scalar(select(User).where(User.username == "dev.temp.user"))

    assert platform_admin is not None
    assert platform_admin.must_change_password is False
    assert platform_admin.password_hash is not None
    assert platform_admin.password_changed_at is not None
    assert platform_admin.password_expires_at is not None

    assert temp_user is not None
    assert temp_user.must_change_password is True
    assert temp_user.password_hash is not None


def test_seed_does_not_reset_existing_password_state(db_session: Session) -> None:
    run_seed(db_session)
    platform_admin = db_session.scalar(select(User).where(User.username == "dev.platform.admin"))
    assert platform_admin is not None
    original_hash = platform_admin.password_hash
    original_changed_at = platform_admin.password_changed_at
    original_expires_at = platform_admin.password_expires_at
    platform_admin.must_change_password = False
    db_session.commit()

    run_seed(db_session)
    db_session.refresh(platform_admin)

    assert platform_admin.password_hash == original_hash
    assert platform_admin.password_changed_at == original_changed_at
    assert platform_admin.password_expires_at == original_expires_at
    assert platform_admin.must_change_password is False


def test_seed_creates_all_four_demo_scenarios(db_session: Session) -> None:
    result = run_seed(db_session)

    request_numbers = {request.request_number for request in result.requests}
    assert request_numbers == set(DEMO_REQUEST_NUMBERS.values())
    assert all(request.status == "ASSIGNED" for request in result.requests)


def test_seed_assignments_match_expected_contractors(db_session: Session) -> None:
    run_seed(db_session)
    access_contractor = db_session.scalar(select(Contractor).where(Contractor.code == DEMO_CONTRACTOR_ACCESS_CODE))
    cctv_contractor = db_session.scalar(select(Contractor).where(Contractor.code == DEMO_CONTRACTOR_CCTV_CODE))
    access_control = db_session.scalar(select(WorkType).where(WorkType.code == "ACCESS_CONTROL"))
    cctv = db_session.scalar(select(WorkType).where(WorkType.code == "CCTV"))

    requests = {
        request.request_number: request
        for request in db_session.scalars(select(ContractorRequest)).all()
    }

    both_one = requests[DEMO_REQUEST_NUMBERS["BOTH_ONE"]]
    both_one_assignments = {assignment.work_type_id: assignment.contractor_id for assignment in both_one.assignments}
    assert both_one_assignments == {
        access_control.id: access_contractor.id,
        cctv.id: access_contractor.id,
    }

    both_split = requests[DEMO_REQUEST_NUMBERS["BOTH_SPLIT"]]
    both_split_assignments = {assignment.work_type_id: assignment.contractor_id for assignment in both_split.assignments}
    assert both_split_assignments == {
        access_control.id: access_contractor.id,
        cctv.id: cctv_contractor.id,
    }


def test_seed_is_blocked_in_production_environment(db_session: Session) -> None:
    original_environment = settings.environment
    settings.environment = "production"
    try:
        with pytest.raises(RuntimeError, match="blocked in production"):
            run_seed(db_session)
    finally:
        settings.environment = original_environment
