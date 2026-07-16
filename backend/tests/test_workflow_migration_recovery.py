from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.scripts.recover_partial_workflow_migration import (
    BASE_REVISION,
    inspect_database,
    recover_database,
)
from app.scripts.seed_demo import run_seed
from app.services.rbac_service import seed_rbac


def configure_database(monkeypatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "migration.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path.as_posix()}")
    return database_path


def alembic_config() -> Config:
    return Config("alembic.ini")


def current_revision(database_path: Path) -> str:
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            return connection.execute(text("select version_num from alembic_version")).scalar_one()
    finally:
        engine.dispose()


def workflow_permission_role_mapping_count(database_path: Path) -> int:
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            return connection.execute(
                text(
                    "select count(*) from role_permissions "
                    "join permissions on permissions.id = role_permissions.permission_id "
                    "where permissions.code like 'workflows.%'"
                )
            ).scalar_one()
    finally:
        engine.dispose()


def test_clean_database_upgrades_to_head(monkeypatch, tmp_path: Path) -> None:
    database_path = configure_database(monkeypatch, tmp_path)

    command.upgrade(alembic_config(), "head")

    assert current_revision(database_path) == "20260716_0010"


def test_0008_database_with_preseeded_workflow_permissions_upgrades_to_head(monkeypatch, tmp_path: Path) -> None:
    database_path = configure_database(monkeypatch, tmp_path)
    config = alembic_config()
    command.upgrade(config, BASE_REVISION)

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as session:
            seed_rbac(session)
        before_count = workflow_permission_role_mapping_count(database_path)
        assert before_count > 0
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    assert current_revision(database_path) == "20260716_0010"
    assert workflow_permission_role_mapping_count(database_path) == before_count


def test_partial_workflow_migration_recovery_preserves_non_workflow_data(monkeypatch, tmp_path: Path) -> None:
    database_path = configure_database(monkeypatch, tmp_path)
    config = alembic_config()
    command.upgrade(config, BASE_REVISION)

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("insert into permissions (id, code, name, resource, action, is_system, is_active) values ('11111111111111111111111111111111', 'recover.test', 'Recover', 'recover', 'test', 1, 1)"))
            connection.execute(text("create table workflow_definitions (id varchar primary key)"))
            connection.execute(text("create table workflow_states (id varchar primary key, workflow_definition_id varchar)"))
            connection.execute(text("create index ix_workflow_states_workflow_definition_id on workflow_states (workflow_definition_id)"))
            connection.execute(text("create table domain_event_outbox (id varchar primary key)"))
    finally:
        engine.dispose()

    dry_run, backup_path = recover_database(database_path, apply=False)
    assert backup_path is None
    assert {table.name for table in dry_run.existing_workflow_tables} == {
        "domain_event_outbox",
        "workflow_states",
        "workflow_definitions",
    }

    recovered, backup_path = recover_database(database_path, apply=True)

    assert backup_path is not None
    assert backup_path.exists()
    assert recovered.alembic_revision == BASE_REVISION
    assert all(not table.exists for table in recovered.workflow_tables)
    assert recovered.preserved_counts["permissions"] == dry_run.preserved_counts["permissions"]

    command.upgrade(config, "head")
    assert current_revision(database_path) == "20260716_0010"

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as session:
            run_seed(session)
            run_seed(session)
        inspection = inspect_database(database_path)
        assert all(table.exists for table in inspection.workflow_tables)
    finally:
        engine.dispose()
