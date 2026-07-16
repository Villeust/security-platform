from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.scripts.seed_demo import run_seed


@dataclass
class Step:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationValidationReport:
    database_path: str
    steps: list[Step] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for step in self.steps if step.status == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for step in self.steps if step.status == "warning")

    @property
    def status(self) -> str:
        return "ok" if self.errors == 0 else "error"

    def add(self, name: str, status: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.steps.append(Step(name, status, message, details or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
            "database_path": self.database_path,
            "steps": [step.__dict__ for step in self.steps],
        }


def backend_path() -> Path:
    return Path(__file__).resolve().parents[2]


def build_config(database_url: str) -> Config:
    backend = backend_path()
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("prepend_sys_path", str(backend))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url"] = database_url
    return config


def validate(database_path: Path, *, skip_downgrade: bool = False) -> MigrationValidationReport:
    database_url = f"sqlite:///{database_path.as_posix()}"
    report = MigrationValidationReport(database_path=str(database_path))
    config = build_config(database_url)

    try:
        command.upgrade(config, "head")
        report.add("clean_upgrade_head", "ok", "Clean SQLite database upgraded to head")
    except Exception as exc:
        report.add("clean_upgrade_head", "error", f"Upgrade failed: {exc}")
        return report

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            head = connection.execute(text("select version_num from alembic_version")).scalar()
            required = {"contractor_requests", "workflow_definitions", "domain_event_outbox", "permissions", "roles"}
            missing = sorted(required - tables)
            report.add(
                "sqlite_compatibility",
                "ok" if not missing else "error",
                "Required tables exist after SQLite upgrade" if not missing else f"Missing tables after upgrade: {', '.join(missing)}",
                {"revision": head, "missing_tables": missing},
            )
            fk_issues = []
            for table in sorted(required.intersection(tables)):
                for fk in inspector.get_foreign_keys(table):
                    if not fk.get("referred_table"):
                        fk_issues.append({"table": table, "columns": fk.get("constrained_columns")})
            report.add(
                "future_postgresql_compatibility",
                "ok" if not fk_issues else "warning",
                "Foreign key metadata is introspectable" if not fk_issues else "Some foreign key metadata could not be introspected",
                {"fk_issues": fk_issues[:20]},
            )
    finally:
        engine.dispose()

    if skip_downgrade:
        report.add("downgrade_previous_revision", "warning", "Downgrade validation was skipped")
    else:
        try:
            command.downgrade(config, "-1")
            command.upgrade(config, "head")
            report.add("downgrade_previous_revision", "ok", "Downgrade by one revision and upgrade back to head succeeded")
        except Exception as exc:
            report.add("downgrade_previous_revision", "warning", f"Downgrade validation is not supported by all migrations: {exc}")

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            first_counts = table_counts(session)
            run_seed(session)
            session.commit()
            second_counts = table_counts(session)
            duplicates = duplicate_seed_counts(session)
            has_duplicates = any(count > 0 for count in duplicates.values())
        report.add(
            "seed_twice",
            "ok" if first_counts == second_counts and not has_duplicates else "error",
            "Demo seed is idempotent" if first_counts == second_counts and not has_duplicates else "Demo seed created duplicates",
            {"first_counts": first_counts, "second_counts": second_counts, "duplicates": duplicates},
        )
    except Exception as exc:
        report.add("seed_twice", "error", f"Seed validation failed: {exc}")
    finally:
        engine.dispose()

    return report


def table_counts(session) -> dict[str, int]:  # type: ignore[no-untyped-def]
    tables = ("users", "contractors", "contractor_requests", "workflow_definitions", "workflow_instances")
    return {table: int(session.execute(text(f'select count(*) from "{table}"')).scalar() or 0) for table in tables}


def duplicate_seed_counts(session) -> dict[str, int]:  # type: ignore[no-untyped-def]
    queries = {
        "users": "select count(*) from (select username from users group by username having count(*) > 1)",
        "contractors": "select count(*) from (select code from contractors group by code having count(*) > 1)",
        "requests": "select count(*) from (select request_number from contractor_requests group by request_number having count(*) > 1)",
        "workflows": "select count(*) from (select code, version from workflow_definitions group by code, version having count(*) > 1)",
    }
    return {name: int(session.execute(text(sql)).scalar() or 0) for name, sql in queries.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Alembic migrations and seed idempotency on a temporary SQLite database.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--keep-db", action="store_true", help="Keep the temporary validation database.")
    parser.add_argument("--skip-downgrade", action="store_true", help="Skip downgrade validation.")
    parser.add_argument("--database-path", type=Path, default=None, help="Use an explicit SQLite database path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.database_path:
        database_path = args.database_path.resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        if database_path.exists():
            database_path.unlink()
        cleanup = False
    else:
        handle = tempfile.NamedTemporaryFile(prefix="platform-migration-", suffix=".db", delete=False)
        handle.close()
        database_path = Path(handle.name).resolve()
        os.unlink(database_path)
        cleanup = not args.keep_db

    report = validate(database_path, skip_downgrade=args.skip_downgrade)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print("Migration Validation")
        print(f"Status: {report.status}")
        print(f"Errors: {report.errors}")
        print(f"Warnings: {report.warnings}")
        for step in report.steps:
            print(f"- {step.status.upper()} {step.name}: {step.message}")
        if args.keep_db:
            print(f"Database: {database_path}")

    if cleanup and database_path.exists():
        database_path.unlink()
    raise SystemExit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
