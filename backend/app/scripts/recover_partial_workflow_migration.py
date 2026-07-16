from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


BASE_REVISION = "20260715_0008"
WORKFLOW_TABLES_DROP_ORDER = [
    "domain_event_outbox",
    "workflow_sla_timers",
    "workflow_sla_policies",
    "workflow_idempotency_records",
    "workflow_transition_executions",
    "workflow_instances",
    "workflow_transitions",
    "workflow_states",
    "workflow_definitions",
]
PRESERVED_TABLES = ["permissions", "roles", "role_permissions", "users", "contractor_requests"]


@dataclass(frozen=True)
class TableState:
    name: str
    exists: bool
    row_count: int | None
    indexes: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryInspection:
    database_path: Path
    alembic_revision: str | None
    workflow_tables: tuple[TableState, ...]
    preserved_counts: dict[str, int | None]

    @property
    def existing_workflow_tables(self) -> tuple[TableState, ...]:
        return tuple(table for table in self.workflow_tables if table.exists)

    @property
    def nonempty_workflow_tables(self) -> tuple[TableState, ...]:
        return tuple(table for table in self.workflow_tables if table.exists and table.row_count not in (None, 0))


def _read_database_url_from_env_file(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "DATABASE_URL":
            return value.strip().strip('"').strip("'")
    return None


def resolve_database_url(explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    for env_path in (Path(".env"), Path("..") / ".env"):
        file_url = _read_database_url_from_env_file(env_path)
        if file_url:
            return file_url
    from app.core.config import settings

    return settings.database_url


def sqlite_path_from_database_url(database_url: str, base_dir: Path | None = None) -> Path:
    if database_url == "sqlite://":
        raise RuntimeError("In-memory SQLite databases cannot be recovered by this script")
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("Recovery script only supports SQLite DATABASE_URL values")

    raw_path = database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    if not path.is_absolute():
        path = (base_dir or Path.cwd()) / path
    return path.resolve()


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    return cursor.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table_name,),
    ).fetchone() is not None


def inspect_database(database_path: Path) -> RecoveryInspection:
    if not database_path.exists():
        raise RuntimeError(f"Database file does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        revision = None
        if _table_exists(cursor, "alembic_version"):
            row = cursor.execute("select version_num from alembic_version").fetchone()
            revision = row[0] if row else None

        workflow_tables = []
        for table_name in WORKFLOW_TABLES_DROP_ORDER:
            exists = _table_exists(cursor, table_name)
            row_count = cursor.execute(f'select count(*) from "{table_name}"').fetchone()[0] if exists else None
            indexes = tuple(
                row[0]
                for row in cursor.execute(
                    "select name from sqlite_master where type = 'index' and tbl_name = ? order by name",
                    (table_name,),
                ).fetchall()
            )
            workflow_tables.append(TableState(name=table_name, exists=exists, row_count=row_count, indexes=indexes))

        preserved_counts = {}
        for table_name in PRESERVED_TABLES:
            preserved_counts[table_name] = (
                cursor.execute(f'select count(*) from "{table_name}"').fetchone()[0]
                if _table_exists(cursor, table_name)
                else None
            )

    return RecoveryInspection(
        database_path=database_path,
        alembic_revision=revision,
        workflow_tables=tuple(workflow_tables),
        preserved_counts=preserved_counts,
    )


def create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.workflow-recovery-{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def recover_database(database_path: Path, apply: bool) -> tuple[RecoveryInspection, Path | None]:
    before = inspect_database(database_path)
    if before.alembic_revision != BASE_REVISION:
        raise RuntimeError(
            f"Expected Alembic revision {BASE_REVISION} before recovery; found {before.alembic_revision!r}"
        )
    if before.nonempty_workflow_tables:
        names = ", ".join(f"{table.name}({table.row_count})" for table in before.nonempty_workflow_tables)
        raise RuntimeError(f"Refusing to drop non-empty workflow-owned tables: {names}")

    if not apply:
        return before, None

    backup_path = create_backup(database_path)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        for table in before.existing_workflow_tables:
            cursor.execute(f'drop table if exists "{table.name}"')
        cursor.execute("PRAGMA foreign_keys=ON")
        connection.commit()
    return inspect_database(database_path), backup_path


def print_report(inspection: RecoveryInspection, backup_path: Path | None, apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"mode={mode}")
    print(f"database={inspection.database_path}")
    print(f"alembic_revision={inspection.alembic_revision}")
    if backup_path is not None:
        print(f"backup={backup_path}")
    print("workflow_owned_tables:")
    for table in inspection.workflow_tables:
        indexes = ",".join(table.indexes) if table.indexes else "-"
        print(f"  {table.name}: exists={table.exists} rows={table.row_count} indexes={indexes}")
    print("preserved_table_counts:")
    for table_name, count in inspection.preserved_counts.items():
        print(f"  {table_name}: rows={count}")
    if not apply:
        print("next_step=rerun with --apply, then run: uv run alembic upgrade head")
    else:
        print("next_step=run: uv run alembic upgrade head")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover a failed partial 0009 workflow migration on local SQLite DBs.")
    parser.add_argument("--database-url", help="SQLite DATABASE_URL to recover. Defaults to DATABASE_URL/.env/settings.")
    parser.add_argument("--dry-run", action="store_true", help="Print the recovery report without changing the database. This is the default.")
    parser.add_argument("--apply", action="store_true", help="Apply recovery. Without this flag, only prints a dry-run report.")
    args = parser.parse_args()

    database_url = resolve_database_url(args.database_url)
    database_path = sqlite_path_from_database_url(database_url)
    inspection, backup_path = recover_database(database_path, apply=args.apply)
    print_report(inspection, backup_path, apply=args.apply)


if __name__ == "__main__":
    main()
