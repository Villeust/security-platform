import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models.admin  # noqa: F401
import app.models.reference_data  # noqa: F401
import app.models.requests  # noqa: F401
import app.models.workflow  # noqa: F401
import app.models.notifications  # noqa: F401
from app.db.base import Base
from app.core.version import platform_version
from app.scripts.platform_doctor import ERROR, OK, WARNING, DoctorReport, render_summary, render_text, run_doctor
from app.services.contractor_request_workflow import seed_contractor_request_workflow_definition
from app.services.rbac_service import seed_rbac

HEAD_REVISION = "20260717_0012"

def write_env(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite:///doctor.db",
                "BACKEND_CORS_ORIGINS=http://127.0.0.1:3000",
                "AUTH_TOKEN_SECRET=test-secret",
                "CONNECTION_SECRETS_KEY=test-secret-key",
            ]
        ),
        encoding="utf-8",
    )
    return path


def prepare_database(tmp_path: Path, *, revision: str = HEAD_REVISION, seed_workflow: bool = True, seed_permissions: bool = True) -> Path:
    database_path = tmp_path / "doctor.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("create table alembic_version (version_num varchar(32) not null)"))
        connection.execute(text("insert into alembic_version (version_num) values (:revision)"), {"revision": revision})
    if seed_permissions or seed_workflow:
        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as session:
            if seed_permissions:
                seed_rbac(session)
            if seed_workflow:
                seed_contractor_request_workflow_definition(session)
                session.commit()
    engine.dispose()
    return database_path


def run_for_db(tmp_path: Path, database_path: Path, *, env_path: Path | None = None, storage_path: Path | None = None, runtime_path: Path | None = None, fix: bool = False) -> DoctorReport:
    backend_path = Path.cwd()
    root_path = backend_path.parent
    return run_doctor(
        root_path=root_path,
        backend_path=backend_path,
        env_path=env_path or write_env(tmp_path / ".env"),
        database_url=f"sqlite:///{database_path.as_posix()}",
        storage_path=storage_path or tmp_path / "storage",
        runtime_path=runtime_path or tmp_path / ".dev-runtime",
        fix=fix,
    )


def section(report: DoctorReport, name: str):
    return next(item for item in report.sections if item.name == name)


def check(report: DoctorReport, section_name: str, check_name: str):
    return next(item for item in section(report, section_name).checks if item.name == check_name)


def test_platform_doctor_healthy_project_has_no_errors(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    storage_path = tmp_path / "storage"
    storage_path.mkdir()

    report = run_for_db(tmp_path, database_path, storage_path=storage_path)

    assert report.errors == 0
    assert section(report, "Workflow").status == OK
    assert section(report, "RBAC").status == OK
    assert check(report, "Seed", "workflow_definition").status == OK


def test_platform_doctor_reports_missing_storage_and_fix_creates_it(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    storage_path = tmp_path / "missing-storage"

    report = run_for_db(tmp_path, database_path, storage_path=storage_path)
    assert check(report, "Storage", "backend_storage_exists").status == WARNING
    assert not storage_path.exists()

    fixed = run_for_db(tmp_path, database_path, storage_path=storage_path, fix=True)
    assert storage_path.exists()
    assert any("Created storage folder" in item for item in fixed.fixes_applied)


def test_platform_doctor_reports_missing_workflow_tables(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("drop table workflow_definitions"))
    engine.dispose()

    report = run_for_db(tmp_path, database_path)

    assert report.errors > 0
    assert check(report, "Workflow", "WorkflowDefinition").status == ERROR


def test_platform_doctor_reports_revision_mismatch_and_partial_migration(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path, revision="20260715_0008")

    report = run_for_db(tmp_path, database_path)

    assert check(report, "Alembic", "revision_match").status == ERROR
    partial = check(report, "Migration Diagnostics", "partial_workflow_migration")
    assert partial.status == ERROR
    assert "recover_partial_workflow_migration --dry-run" in (partial.recommendation or "")


def test_platform_doctor_reports_duplicate_role_permissions(tmp_path: Path) -> None:
    database_path = tmp_path / "duplicates.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("create table alembic_version (version_num varchar(32) not null)"))
        connection.execute(text("insert into alembic_version values (:revision)"), {"revision": HEAD_REVISION})
        connection.execute(text("create table roles (id varchar, code varchar)"))
        connection.execute(text("create table permissions (id varchar, code varchar)"))
        connection.execute(text("create table role_permissions (role_id varchar, permission_id varchar)"))
        connection.execute(text("insert into roles values ('role-1', 'PLATFORM_ADMIN')"))
        connection.execute(text("insert into permissions values ('perm-1', 'workflows.view')"))
        connection.execute(text("insert into role_permissions values ('role-1', 'perm-1')"))
        connection.execute(text("insert into role_permissions values ('role-1', 'perm-1')"))
    engine.dispose()

    report = run_for_db(tmp_path, database_path)

    assert check(report, "RBAC", "duplicate_mappings").status == ERROR
    assert check(report, "Migration Diagnostics", "duplicate_role_permissions").status == ERROR


def test_platform_doctor_reports_missing_workflow_definition(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path, seed_workflow=False)

    report = run_for_db(tmp_path, database_path)

    assert check(report, "Seed", "workflow_definition").status == ERROR
    assert check(report, "Migration Diagnostics", "missing_workflow_definition").status == ERROR


def test_platform_doctor_reports_missing_env(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)

    report = run_for_db(tmp_path, database_path, env_path=tmp_path / "missing.env")

    assert check(report, "Configuration", ".env").status == WARNING


def test_platform_doctor_json_output_is_machine_readable(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)

    report = run_for_db(tmp_path, database_path)
    payload = json.loads(json.dumps(report.to_dict()))

    assert payload["error_count"] == report.errors
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["checks"], list)
    assert payload["health"] == report.health_percent
    assert payload["health_percent"] == report.health_percent
    assert payload["status"] in {"healthy", "unhealthy"}
    assert payload["version"] == platform_version()
    assert payload["environment"]
    assert any(item["name"] == "Workflow" for item in payload["sections"])


def test_platform_doctor_summary_output(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)

    report = run_for_db(tmp_path, database_path)
    output = render_summary(report)

    assert "Platform Health:" in output
    assert "Errors:" in output
    assert "Warnings:" in output
    assert "Version: 0.8.0" in output


def test_platform_doctor_core_security_and_infrastructure_categories(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    storage_path = tmp_path / "storage"
    storage_path.mkdir()

    report = run_for_db(tmp_path, database_path, storage_path=storage_path)

    assert check(report, "Core", "Platform Version").status == OK
    assert check(report, "Core", "Readiness").status == OK
    assert check(report, "Security", "CSRF").status == OK
    assert check(report, "Security", "CORS").status == OK
    assert check(report, "Infrastructure", "Startup Scripts").status == OK
    assert check(report, "Infrastructure", "Stop Scripts").status == OK
    assert check(report, "Optional integrations", "SMTP").status == WARNING


def test_platform_doctor_fix_mode_clears_stale_runtime_files(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    runtime_path = tmp_path / ".dev-runtime"
    runtime_path.mkdir()
    pid_file = runtime_path / "processes.json"
    lock_file = runtime_path / "server.lock"
    pid_file.write_text(json.dumps({"backend": {"pid": 999999}}), encoding="utf-8")
    lock_file.write_text("stale", encoding="utf-8")

    report = run_for_db(tmp_path, database_path, runtime_path=runtime_path, fix=True)

    assert not pid_file.exists()
    assert not lock_file.exists()
    assert any("Removed stale pid file" in item for item in report.fixes_applied)
    assert any("Removed stale lock file" in item for item in report.fixes_applied)
    assert "Platform Health" in render_text(report, no_color=True)
