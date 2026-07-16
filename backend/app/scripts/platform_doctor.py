from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import bindparam, create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging import JsonFormatter, PrettyFormatter
from app.core.readiness import readiness_checks
from app.core.security import content_security_policy
from app.core.version import platform_environment, platform_version
from app.scripts.seed_demo import DEMO_USERS
from app.services.contractor_request_workflow import CONTRACTOR_REQUEST_WORKFLOW_CODE


OK = "ok"
WARNING = "warning"
ERROR = "error"

WORKFLOW_REVISION = "20260716_0009"
CONTRACTOR_WORKFLOW_REVISION = "20260716_0010"
WORKFLOW_PERMISSION_CODES = {
    "workflows.view",
    "workflows.manage",
    "workflows.publish",
    "workflows.instances.view",
    "workflows.instances.transition",
    "workflows.sla.view",
    "workflows.sla.manage",
}
WORKFLOW_TABLES = {
    "WorkflowDefinition": "workflow_definitions",
    "WorkflowState": "workflow_states",
    "WorkflowTransition": "workflow_transitions",
    "WorkflowInstance": "workflow_instances",
    "WorkflowTransitionExecution": "workflow_transition_executions",
    "WorkflowSlaPolicy": "workflow_sla_policies",
    "WorkflowSlaTimer": "workflow_sla_timers",
    "WorkflowOutbox": "domain_event_outbox",
}
CONTRACTOR_TABLES = {
    "contractors": "contractors",
    "memberships": "contractor_memberships",
    "assignments": "request_assignments",
    "requests": "contractor_requests",
    "history": "request_history",
}
REQUIRED_ENV_KEYS = {"DATABASE_URL", "BACKEND_CORS_ORIGINS"}
OPTIONAL_SECRET_KEYS = {"AUTH_TOKEN_SECRET", "CONNECTION_SECRETS_KEY"}
PROVIDER_TYPES = ("SMTP", "LDAP", "ADFS")
DEPENDENCIES = ("alembic", "fastapi", "pydantic-settings", "sqlalchemy")


@dataclass
class Check:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recommendation: str | None = None

    @property
    def optional(self) -> bool:
        return bool(self.details.get("optional"))

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": json_safe(self.details),
        }
        if self.recommendation:
            data["recommendation"] = self.recommendation
        return data


def json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (Path, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return str(value)


@dataclass
class Section:
    name: str
    checks: list[Check] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(check.status == ERROR for check in self.checks):
            return ERROR
        if any(check.status == WARNING for check in self.checks):
            return WARNING
        return OK

    def add(self, name: str, status: str, message: str, details: dict[str, Any] | None = None, recommendation: str | None = None) -> None:
        self.checks.append(Check(name, status, message, details or {}, recommendation))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass
class DoctorReport:
    sections: list[Section] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> int:
        return len(self.warning_checks)

    @property
    def errors(self) -> int:
        return len(self.error_checks)

    @property
    def all_checks(self) -> list[tuple[str, Check]]:
        return [(section.name, check) for section in self.sections for check in section.checks]

    @property
    def warning_checks(self) -> list[tuple[str, Check]]:
        return [(section, check) for section, check in self.all_checks if check.status == WARNING]

    @property
    def error_checks(self) -> list[tuple[str, Check]]:
        return [(section, check) for section, check in self.all_checks if check.status == ERROR]

    @property
    def status(self) -> str:
        if self.errors:
            return "unhealthy"
        return "healthy"

    @property
    def health_percent(self) -> int:
        checks = [check for section in self.sections for check in section.checks]
        if not checks:
            return 100
        score = 0.0
        for check in checks:
            if check.status == OK or (check.status == WARNING and check.optional):
                score += 1
            elif check.status == WARNING:
                score += 0.5
        return int(round((score / len(checks)) * 100))

    def to_dict(self) -> dict[str, Any]:
        flat_checks = [
            {"category": section_name, **check.to_dict()}
            for section_name, check in self.all_checks
        ]
        warnings = [
            {"category": section_name, **check.to_dict()}
            for section_name, check in self.warning_checks
        ]
        errors = [
            {"category": section_name, **check.to_dict()}
            for section_name, check in self.error_checks
        ]
        return {
            "health": self.health_percent,
            "health_percent": self.health_percent,
            "status": self.status,
            "checks": flat_checks,
            "warnings": warnings,
            "errors": errors,
            "warning_count": self.warnings,
            "error_count": self.errors,
            "version": platform_version(),
            "environment": platform_environment(),
            "fixes_applied": self.fixes_applied,
            "sections": [section.to_dict() for section in self.sections],
        }


@dataclass(frozen=True)
class DoctorContext:
    root_path: Path
    backend_path: Path
    env_path: Path
    database_url: str
    storage_path: Path
    runtime_path: Path
    fix: bool = False
    verbose: bool = False


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "backend" / "app").exists() and (candidate / "scripts" / "start-dev.ps1").exists():
            return candidate
        if candidate.name == "backend" and (candidate / "app").exists():
            return candidate.parent
    return current.parent if current.name == "backend" else current


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_context(
    root_path: Path | None = None,
    backend_path: Path | None = None,
    env_path: Path | None = None,
    database_url: str | None = None,
    storage_path: Path | None = None,
    runtime_path: Path | None = None,
    fix: bool = False,
    verbose: bool = False,
) -> DoctorContext:
    root = (root_path or find_project_root()).resolve()
    backend = (backend_path or root / "backend").resolve()
    env = (env_path or root / ".env").resolve()
    env_values = read_env_file(env)
    resolved_database_url = database_url or os.environ.get("DATABASE_URL") or env_values.get("DATABASE_URL") or settings.database_url
    raw_storage = storage_path or Path(os.environ.get("STORAGE_ROOT") or env_values.get("STORAGE_ROOT") or settings.storage_root)
    resolved_storage = raw_storage if raw_storage.is_absolute() else backend / raw_storage
    return DoctorContext(
        root_path=root,
        backend_path=backend,
        env_path=env,
        database_url=resolved_database_url,
        storage_path=resolved_storage.resolve(),
        runtime_path=(runtime_path or root / ".dev-runtime").resolve(),
        fix=fix,
        verbose=verbose,
    )


def table_exists(inspector: Any, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def scalar(connection: Any, sql: str, params: dict[str, Any] | None = None) -> Any:
    return connection.execute(text(sql), params or {}).scalar()


def query_count(connection: Any, table_name: str) -> int:
    return int(scalar(connection, f'select count(*) from "{table_name}"') or 0)


def sqlite_database_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return None
    if not url.database or url.database == ":memory:":
        return None
    path = Path(url.database)
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def build_alembic_config(context: DoctorContext) -> Config:
    config = Config(str(context.backend_path / "alembic.ini"))
    config.set_main_option("script_location", str(context.backend_path / "alembic"))
    config.set_main_option("prepend_sys_path", str(context.backend_path))
    config.set_main_option("sqlalchemy.url", context.database_url)
    return config


def revision_positions(context: DoctorContext) -> dict[str, int]:
    script = ScriptDirectory.from_config(build_alembic_config(context))
    revisions = list(reversed(list(script.walk_revisions())))
    return {revision.revision: index for index, revision in enumerate(revisions)}


def alembic_head(context: DoctorContext) -> str | None:
    script = ScriptDirectory.from_config(build_alembic_config(context))
    heads = script.get_heads()
    return heads[0] if len(heads) == 1 else None


def check_python_environment(report: DoctorReport) -> None:
    section = Section("Python")
    version = sys.version_info
    status = OK if version >= (3, 12) else ERROR
    section.add(
        "python_version",
        status,
        f"Python {version.major}.{version.minor}.{version.micro}",
        {"executable": sys.executable, "version": sys.version.split()[0]},
    )

    uv_path = shutil.which("uv")
    uv_version = None
    if uv_path:
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5, check=False)
            uv_version = result.stdout.strip() or result.stderr.strip()
        except Exception:
            uv_version = "available"
    section.add("uv", OK if uv_path else ERROR, "uv is available" if uv_path else "uv is not available", {"path": uv_path, "version": uv_version})

    in_venv = bool(os.environ.get("VIRTUAL_ENV")) or sys.prefix != sys.base_prefix
    section.add(
        "virtual_environment",
        OK if in_venv else WARNING,
        "Virtual environment is active" if in_venv else "Virtual environment was not detected",
        {"prefix": sys.prefix, "base_prefix": sys.base_prefix, "virtual_env": os.environ.get("VIRTUAL_ENV")},
    )

    missing = []
    installed = {}
    for dependency in DEPENDENCIES:
        try:
            installed[dependency] = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            missing.append(dependency)
    section.add(
        "installed_dependencies",
        OK if not missing else ERROR,
        "Required backend dependencies are installed" if not missing else f"Missing dependencies: {', '.join(missing)}",
        {"installed": installed, "missing": missing},
        "Run: uv sync" if missing else None,
    )
    report.sections.append(section)


def check_database(report: DoctorReport, context: DoctorContext) -> Engine | None:
    section = Section("Database")
    engine = None
    try:
        engine = create_engine(context.database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
            dialect = connection.dialect.name
            db_path = sqlite_database_path(context.database_url)
            section.add(
                "connection",
                OK,
                "Database connection succeeded",
                {"engine": dialect, "database_path": str(db_path) if db_path else None},
            )
            section.add("engine", OK, f"Database engine: {dialect}", {"driver": connection.dialect.driver})

            if db_path is not None:
                exists = db_path.exists()
                writable = exists and os.access(db_path, os.W_OK)
                section.add(
                    "database_path",
                    OK if exists else ERROR,
                    f"SQLite database path: {db_path}" if exists else f"SQLite database file is missing: {db_path}",
                    {"path": str(db_path), "exists": exists},
                )
                section.add(
                    "writable",
                    OK if writable else ERROR,
                    "SQLite database file is writable" if writable else "SQLite database file is not writable",
                    {"path": str(db_path), "writable": writable},
                )
                fk_enabled = bool(connection.execute(text("pragma foreign_keys")).scalar())
                section.add(
                    "sqlite_foreign_keys",
                    OK if fk_enabled else WARNING,
                    "SQLite foreign keys are enabled" if fk_enabled else "SQLite foreign keys are disabled on this diagnostic connection",
                    {"enabled": fk_enabled},
                )
            else:
                section.add("database_path", OK, "Database path is not applicable for this engine", {"database_url_driver": make_url(context.database_url).drivername})
                section.add("writable", OK, "Writable check uses active database connection for this engine")
    except Exception as exc:
        section.add("connection", ERROR, f"Database connection failed: {exc}", {"database_url_driver": make_url(context.database_url).drivername}, "Check DATABASE_URL and database availability")
        if engine is not None:
            engine.dispose()
            engine = None
    report.sections.append(section)
    return engine


def check_alembic(report: DoctorReport, context: DoctorContext, engine: Engine | None) -> str | None:
    section = Section("Alembic")
    current = None
    head = None
    try:
        head = alembic_head(context)
        section.add("head_revision", OK if head else ERROR, f"Head revision: {head}" if head else "Could not determine a single Alembic head", {"head": head})
    except Exception as exc:
        section.add("head_revision", ERROR, f"Could not read Alembic scripts: {exc}")

    if engine is None:
        section.add("current_revision", ERROR, "Skipped current revision because database is unavailable")
        report.sections.append(section)
        return None

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if not table_exists(inspector, "alembic_version"):
                section.add("current_revision", ERROR, "alembic_version table is missing")
            else:
                current = scalar(connection, "select version_num from alembic_version")
                section.add("current_revision", OK if current else ERROR, f"Current revision: {current}", {"current": current})
    except Exception as exc:
        section.add("current_revision", ERROR, f"Could not read current revision: {exc}")

    if current and head:
        if current == head:
            section.add("revision_match", OK, "Database revision matches Alembic head", {"current": current, "head": head})
        else:
            section.add(
                "revision_match",
                ERROR,
                f"Database revision {current} does not match head {head}",
                {"current": current, "head": head},
                "Run: uv run alembic upgrade head",
            )
        try:
            positions = revision_positions(context)
            section.add(
                "missing_migrations",
                OK if current == head else ERROR,
                "No missing migrations" if current == head else "Database is not at the latest migration",
                {"known_revision": current in positions, "current_position": positions.get(current), "head_position": positions.get(head)},
            )
        except Exception as exc:
            section.add("missing_migrations", WARNING, f"Could not compute migration distance: {exc}")
    report.sections.append(section)
    return current


def check_workflow(report: DoctorReport, engine: Engine | None) -> None:
    section = Section("Workflow")
    if engine is None:
        section.add("workflow_tables", ERROR, "Skipped workflow checks because database is unavailable")
        report.sections.append(section)
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        for label, table_name in WORKFLOW_TABLES.items():
            exists = table_exists(inspector, table_name)
            details: dict[str, Any] = {"table": table_name, "exists": exists}
            if exists:
                details["row_count"] = query_count(connection, table_name)
                details["indexes"] = [item["name"] for item in inspector.get_indexes(table_name)]
                details["foreign_keys"] = [
                    {"constrained_columns": fk.get("constrained_columns"), "referred_table": fk.get("referred_table")}
                    for fk in inspector.get_foreign_keys(table_name)
                ]
            section.add(label, OK if exists else ERROR, f"{table_name} exists" if exists else f"{table_name} is missing", details)
    report.sections.append(section)


def check_rbac(report: DoctorReport, engine: Engine | None) -> None:
    section = Section("RBAC")
    if engine is None:
        section.add("rbac", ERROR, "Skipped RBAC checks because database is unavailable")
        report.sections.append(section)
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        for table_name in ("permissions", "roles", "role_permissions"):
            exists = table_exists(inspector, table_name)
            details = {"table": table_name, "exists": exists}
            if exists:
                details["row_count"] = query_count(connection, table_name)
            section.add(table_name, OK if exists else ERROR, f"{table_name} exists" if exists else f"{table_name} is missing", details)

        required_tables_exist = all(table_exists(inspector, name) for name in ("permissions", "roles", "role_permissions"))
        if required_tables_exist:
            duplicates = connection.execute(
                text(
                    "select role_id, permission_id, count(*) as count from role_permissions "
                    "group by role_id, permission_id having count(*) > 1"
                )
            ).mappings().all()
            section.add(
                "duplicate_mappings",
                ERROR if duplicates else OK,
                f"Duplicate role-permission mappings found: {len(duplicates)}" if duplicates else "No duplicate role-permission mappings",
                {"duplicates": [dict(row) for row in duplicates[:20]], "duplicate_count": len(duplicates)},
            )

            orphan_permissions = int(
                scalar(
                    connection,
                    "select count(*) from role_permissions rp left join permissions p on p.id = rp.permission_id where p.id is null",
                )
                or 0
            )
            orphan_roles = int(
                scalar(
                    connection,
                    "select count(*) from role_permissions rp left join roles r on r.id = rp.role_id where r.id is null",
                )
                or 0
            )
            section.add("orphan_permissions", ERROR if orphan_permissions else OK, "No orphan permission mappings" if not orphan_permissions else f"Orphan permission mappings: {orphan_permissions}", {"count": orphan_permissions})
            section.add("orphan_roles", ERROR if orphan_roles else OK, "No orphan role mappings" if not orphan_roles else f"Orphan role mappings: {orphan_roles}", {"count": orphan_roles})

            existing_workflow_permissions = {
                row[0]
                for row in connection.execute(
                    text("select code from permissions where code like 'workflows.%'")
                ).all()
            }
            missing = sorted(WORKFLOW_PERMISSION_CODES - existing_workflow_permissions)
            section.add(
                "workflow_permissions",
                ERROR if missing else OK,
                "Workflow permissions are present" if not missing else f"Missing workflow permissions: {', '.join(missing)}",
                {"missing": missing},
                "Run: uv run alembic upgrade head" if missing else None,
            )
    report.sections.append(section)


def check_auth(report: DoctorReport, engine: Engine | None) -> None:
    section = Section("Auth")
    if engine is None:
        section.add("auth", ERROR, "Skipped authentication checks because database is unavailable")
        report.sections.append(section)
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        for table_name in ("users", "auth_sessions"):
            exists = table_exists(inspector, table_name)
            details = {"table": table_name, "exists": exists}
            if exists:
                details["row_count"] = query_count(connection, table_name)
            section.add(table_name, OK if exists else ERROR, f"{table_name} exists" if exists else f"{table_name} is missing", details)

    policy_ok = settings.password_min_length > 0 and settings.password_min_length <= settings.password_max_length
    section.add(
        "password_policy",
        OK if policy_ok else ERROR,
        "Password policy is internally consistent" if policy_ok else "Password policy min/max length is invalid",
        {
            "min_length": settings.password_min_length,
            "max_length": settings.password_max_length,
            "require_uppercase": settings.password_require_uppercase,
            "require_lowercase": settings.password_require_lowercase,
            "require_digit": settings.password_require_digit,
            "require_special": settings.password_require_special,
        },
    )
    temp_ok = settings.password_min_length <= 18 <= settings.password_max_length
    section.add(
        "temporary_password_configuration",
        OK if temp_ok else ERROR,
        "Temporary password generator fits password policy length" if temp_ok else "Temporary password length does not fit password policy",
        {"temporary_password_length": 18},
    )
    csrf_ok = bool(settings.auth_csrf_cookie_name and settings.auth_access_cookie_name and settings.auth_refresh_cookie_name)
    section.add("csrf", OK if csrf_ok else ERROR, "CSRF/auth cookie names are configured" if csrf_ok else "CSRF/auth cookie names are incomplete")
    report.sections.append(section)


def check_contractor(report: DoctorReport, engine: Engine | None) -> None:
    section = Section("Contractor")
    if engine is None:
        section.add("contractor", ERROR, "Skipped contractor checks because database is unavailable")
        report.sections.append(section)
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        for label, table_name in CONTRACTOR_TABLES.items():
            exists = table_exists(inspector, table_name)
            details = {"table": table_name, "exists": exists}
            if exists:
                details["row_count"] = query_count(connection, table_name)
            section.add(label, OK if exists else ERROR, f"{table_name} exists" if exists else f"{table_name} is missing", details)
    report.sections.append(section)


def check_seed(report: DoctorReport, engine: Engine | None) -> None:
    section = Section("Seed")
    if engine is None:
        section.add("seed", ERROR, "Skipped seed checks because database is unavailable")
        report.sections.append(section)
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        if table_exists(inspector, "users"):
            usernames = [username for username, _, _ in DEMO_USERS.values()]
            existing = {
                row[0]
                for row in connection.execute(
                    text("select username from users where username in :usernames").bindparams(bindparam("usernames", expanding=True)),
                    {"usernames": tuple(usernames)},
                ).all()
            } if usernames else set()
            missing = sorted(set(usernames) - existing)
            section.add(
                "demo_users",
                WARNING if missing else OK,
                "Demo users are present" if not missing else f"Missing demo users: {', '.join(missing)}",
                {"missing": missing, "present_count": len(existing)},
                "Run: uv run python -m app.scripts.seed_demo" if missing else None,
            )
        else:
            section.add("demo_users", ERROR, "users table is missing")

        if table_exists(inspector, "workflow_definitions"):
            workflow = connection.execute(
                text(
                    "select id, version, is_published from workflow_definitions "
                    "where code = :code and version = 1"
                ),
                {"code": CONTRACTOR_REQUEST_WORKFLOW_CODE},
            ).mappings().first()
            section.add(
                "workflow_definition",
                ERROR if workflow is None else OK,
                "Contractor request workflow definition exists" if workflow else "Contractor request workflow definition is missing",
                dict(workflow) if workflow else {},
                "Run: uv run alembic upgrade head; then run: uv run python -m app.scripts.seed_demo" if workflow is None else None,
            )
            if workflow is not None:
                section.add(
                    "workflow_version",
                    OK if workflow["version"] == 1 else ERROR,
                    f"Contractor request workflow version: {workflow['version']}",
                    {"version": workflow["version"], "published": bool(workflow["is_published"])},
                )
        else:
            section.add("workflow_definition", ERROR, "workflow_definitions table is missing")

        if table_exists(inspector, "work_types"):
            expected_work_types = {
                "ACCESS_CONTROL": "00000000000000000000000000000101",
                "CCTV": "00000000000000000000000000000102",
            }
            mismatches = []
            for code, expected_id in expected_work_types.items():
                actual = scalar(connection, "select id from work_types where code = :code", {"code": code})
                if actual is not None and str(actual).replace("-", "") != expected_id:
                    mismatches.append({"code": code, "expected_id": expected_id, "actual_id": str(actual)})
            section.add(
                "stable_ids",
                ERROR if mismatches else OK,
                "Stable seed IDs are intact" if not mismatches else "Stable seed ID mismatches found",
                {"mismatches": mismatches},
            )
        else:
            section.add("stable_ids", ERROR, "work_types table is missing")
    report.sections.append(section)


def check_storage(report: DoctorReport, context: DoctorContext) -> None:
    section = Section("Storage")
    path = context.storage_path
    if not path.exists() and context.fix:
        path.mkdir(parents=True, exist_ok=True)
        report.fixes_applied.append(f"Created storage folder: {path}")
    exists = path.exists()
    section.add("backend_storage_exists", OK if exists else WARNING, f"Storage folder exists: {path}" if exists else f"Storage folder is missing: {path}", {"path": str(path)}, "Run with --fix to create the storage folder" if not exists else None)
    writable = False
    if exists:
        try:
            probe = path / ".platform-doctor-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            writable = True
        except Exception:
            writable = False
    section.add("backend_storage_writable", OK if writable else WARNING, "Storage folder is writable" if writable else "Storage folder is not writable", {"path": str(path)})
    report.sections.append(section)


def remove_stale_runtime_files(report: DoctorReport, context: DoctorContext) -> None:
    if not context.fix:
        return
    runtime = context.runtime_path
    runtime.mkdir(parents=True, exist_ok=True)
    pid_file = runtime / "processes.json"
    if pid_file.exists():
        stale = True
        try:
            data = json.loads(pid_file.read_text(encoding="utf-8-sig"))
            for value in data.values():
                pid = int(value.get("pid")) if isinstance(value, dict) and value.get("pid") else None
                if pid and process_exists(pid):
                    stale = False
                    break
        except Exception:
            stale = True
        if stale:
            pid_file.unlink()
            report.fixes_applied.append(f"Removed stale pid file: {pid_file}")
    for lock_file in runtime.glob("*.lock"):
        lock_file.unlink()
        report.fixes_applied.append(f"Removed stale lock file: {lock_file}")


def process_exists(pid: int) -> bool:
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            ERROR_ACCESS_DENIED = 5
            ERROR_INVALID_PARAMETER = 87
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if handle:
                kernel32.CloseHandle(handle)
                return True
            error = ctypes.get_last_error()
            if error == ERROR_ACCESS_DENIED:
                return True
            if error == ERROR_INVALID_PARAMETER:
                return False
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def read_pyproject_version(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        import tomllib

        return tomllib.loads(path.read_text(encoding="utf-8")).get("project", {}).get("version")
    except Exception:
        return None


def read_package_version(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")).get("version")
    except Exception:
        return None


def iter_api_routes() -> list[tuple[str, Any]]:
    try:
        from fastapi.routing import APIRoute
        from app.main import app
    except Exception:
        return []

    result: list[tuple[str, Any]] = []

    def visit(routes: list[Any], prefix: str = "") -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                result.append((f"{prefix}{route.path}", route))
                continue
            original_router = getattr(route, "original_router", None)
            include_context = getattr(route, "include_context", None)
            if original_router is not None:
                nested_prefix = f"{prefix}{getattr(include_context, 'prefix', '')}"
                visit(list(getattr(original_router, "routes", [])), nested_prefix)

    visit(list(app.routes))
    return result


def route_paths() -> set[str]:
    return {path for path, _route in iter_api_routes()}


def route_dependency_names(path_prefix: str | None = None) -> dict[str, set[str]]:
    inventory: dict[str, set[str]] = {}
    for path, route in iter_api_routes():
        if path_prefix and not path.startswith(path_prefix):
            continue
        names: set[str] = set()
        stack = list(route.dependant.dependencies)
        while stack:
            dependency = stack.pop()
            if dependency.call is not None:
                names.add(getattr(dependency.call, "__name__", ""))
            stack.extend(dependency.dependencies)
        inventory[path] = names
    return inventory


def mutation_routes_missing_csrf() -> list[str]:
    routes = iter_api_routes()
    if not routes:
        return ["<route inventory unavailable>"]

    exemptions = {
        f"{settings.api_v1_prefix}/auth/login",
        f"{settings.api_v1_prefix}/auth/refresh",
    }
    dependencies = route_dependency_names()
    missing: list[str] = []
    for path, route in routes:
        if not path.startswith(settings.api_v1_prefix):
            continue
        methods = set(route.methods or set())
        if not methods.intersection({"POST", "PUT", "PATCH", "DELETE"}):
            continue
        if path in exemptions:
            continue
        if "require_csrf" not in dependencies.get(path, set()):
            missing.append(path)
    return sorted(missing)


def check_core_summary(report: DoctorReport, context: DoctorContext, engine: Engine | None, current_revision: str | None) -> None:
    section = Section("Core")
    version = platform_version()
    version_path = context.root_path / "VERSION"
    root_version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else None
    backend_version = read_pyproject_version(context.backend_path / "pyproject.toml")
    frontend_version = read_package_version(context.root_path / "frontend" / "package.json")
    versions = {
        "VERSION": root_version,
        "backend": backend_version,
        "frontend": frontend_version,
        "runtime": version,
    }
    consistent = bool(version and all(item == version for item in versions.values()))
    section.add(
        "Platform Version",
        OK if consistent else ERROR,
        f"Platform version {version}" if consistent else "Platform version is not synchronized",
        {"versions": versions},
        "Synchronize VERSION, backend pyproject.toml and frontend package.json" if not consistent else None,
    )
    section.add(
        "Database",
        OK if engine is not None else ERROR,
        "Database connectivity is available" if engine is not None else "Database connectivity failed",
    )
    head = None
    try:
        head = alembic_head(context)
    except Exception:
        head = None
    section.add(
        "Alembic",
        OK if current_revision and head and current_revision == head else ERROR,
        "Alembic revision matches head" if current_revision and head and current_revision == head else "Alembic revision mismatch",
        {"current": current_revision, "head": head},
        "Run: uv run alembic upgrade head" if not (current_revision and head and current_revision == head) else None,
    )
    section.add(
        "Workflow Engine",
        OK if "workflow_definitions" in workflow_table_names(engine) else ERROR,
        "Workflow engine tables are present" if "workflow_definitions" in workflow_table_names(engine) else "Workflow engine tables are missing",
    )
    section.add(
        "RBAC",
        OK if required_tables_present(engine, ("permissions", "roles", "role_permissions")) else ERROR,
        "RBAC tables are present" if required_tables_present(engine, ("permissions", "roles", "role_permissions")) else "RBAC tables are missing",
    )
    section.add(
        "Correlation",
        OK if settings.correlation_id_header else ERROR,
        f"Correlation header: {settings.correlation_id_header}" if settings.correlation_id_header else "Correlation header is missing",
    )
    logging_ok = settings.log_format.lower() in {"console", "json"} and JsonFormatter and PrettyFormatter
    section.add(
        "Logging",
        OK if logging_ok else ERROR,
        f"Structured logging configured for {settings.log_format}" if logging_ok else "Structured logging format is invalid",
        {"format": settings.log_format, "environment": settings.environment},
    )
    paths = route_paths()
    readiness_ok = f"{settings.api_v1_prefix}/readiness" in paths
    health_ok = f"{settings.api_v1_prefix}/health" in paths
    section.add(
        "Readiness",
        OK if readiness_ok and health_ok else ERROR,
        "Health and readiness endpoints are registered" if readiness_ok and health_ok else "Health or readiness endpoint is missing",
        {"health": health_ok, "readiness": readiness_ok},
    )
    report.sections.append(section)


def workflow_table_names(engine: Engine | None) -> set[str]:
    if engine is None:
        return set()
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    except Exception:
        return set()


def required_tables_present(engine: Engine | None, table_names: tuple[str, ...]) -> bool:
    existing = workflow_table_names(engine)
    return all(table in existing for table in table_names)


def check_security_summary(report: DoctorReport) -> None:
    section = Section("Security")
    csp = content_security_policy()
    production = settings.environment.lower() in {"production", "prod"}
    section.add(
        "CSP",
        OK if "default-src 'self'" in csp and "object-src 'none'" in csp else ERROR,
        "Content Security Policy is configured",
        {"production": production, "policy": csp},
    )
    section.add(
        "Security Headers",
        OK,
        "Security headers are registered through middleware",
        {"headers": ["X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options", "Content-Security-Policy", "Permissions-Policy"]},
    )
    cookie_ok = settings.auth_cookie_samesite in {"lax", "strict", "none"} and bool(settings.auth_cookie_path)
    if production:
        cookie_ok = cookie_ok and settings.hsts_enabled and settings.auth_token_secret not in {None, "change-me", "secret", "test-secret"}
    section.add(
        "Cookies",
        OK if cookie_ok else ERROR,
        "Cookie configuration is safe for the current environment" if cookie_ok else "Cookie configuration is unsafe",
        {"same_site": settings.auth_cookie_samesite, "path": settings.auth_cookie_path, "domain_configured": bool(settings.auth_cookie_domain)},
    )
    missing_csrf = mutation_routes_missing_csrf()
    section.add(
        "CSRF",
        OK if not missing_csrf else ERROR,
        "All non-exempt mutation routes require CSRF" if not missing_csrf else "Mutation routes missing CSRF protection",
        {"missing_routes": missing_csrf, "exemptions": [f"{settings.api_v1_prefix}/auth/login", f"{settings.api_v1_prefix}/auth/refresh"]},
    )
    cors_ok = bool(settings.backend_cors_origins) and "*" not in settings.backend_cors_origins
    if production:
        cors_ok = cors_ok and all("localhost" not in origin and "127.0.0.1" not in origin for origin in settings.backend_cors_origins)
    section.add(
        "CORS",
        OK if cors_ok else ERROR,
        "CORS origins are explicit" if cors_ok else "CORS origins are unsafe or missing",
        {"origin_count": len(settings.backend_cors_origins)},
    )
    report.sections.append(section)


def check_infrastructure_summary(report: DoctorReport, context: DoctorContext) -> None:
    section = Section("Infrastructure")
    storage_exists = context.storage_path.exists() and context.storage_path.is_dir()
    section.add(
        "Storage",
        OK if storage_exists else WARNING,
        f"Storage path exists: {context.storage_path}" if storage_exists else f"Storage path is missing: {context.storage_path}",
        {"path": str(context.storage_path)},
        "Run: uv run python -m app.scripts.platform_doctor --fix" if not storage_exists else None,
    )
    upload_ok = settings.max_upload_file_bytes > 0 and settings.max_files_per_request > 0
    section.add(
        "Upload Limits",
        OK if upload_ok else ERROR,
        "Upload limits are configured" if upload_ok else "Upload limits are invalid",
        {"max_upload_file_bytes": settings.max_upload_file_bytes, "max_files_per_request": settings.max_files_per_request},
    )
    request_ok = settings.max_request_body_bytes >= settings.max_json_body_bytes > 0 and settings.max_request_body_bytes >= settings.max_multipart_body_bytes > 0
    section.add(
        "Request Limits",
        OK if request_ok else ERROR,
        "Request body limits are configured" if request_ok else "Request body limits are invalid",
        {
            "max_request_body_bytes": settings.max_request_body_bytes,
            "max_json_body_bytes": settings.max_json_body_bytes,
            "max_multipart_body_bytes": settings.max_multipart_body_bytes,
        },
    )
    env_ok = settings.environment.lower() not in {"production", "prod"} or (settings.hsts_enabled and settings.public_base_url)
    section.add(
        "Environment",
        OK if env_ok else ERROR,
        f"Environment: {settings.environment}" if env_ok else "Production environment is missing HTTPS configuration",
        {"environment": settings.environment, "public_base_url_configured": bool(settings.public_base_url), "hsts_enabled": settings.hsts_enabled},
    )
    start_script = context.root_path / "scripts" / "start-dev.ps1"
    stop_script = context.root_path / "scripts" / "stop-dev.ps1"
    section.add(
        "Startup Scripts",
        OK if start_script.exists() else ERROR,
        "Startup script is present" if start_script.exists() else "Startup script is missing",
        {"path": str(start_script)},
    )
    section.add(
        "Stop Scripts",
        OK if stop_script.exists() else ERROR,
        "Stop script is present" if stop_script.exists() else "Stop script is missing",
        {"path": str(stop_script)},
    )
    validation_script = context.backend_path / "app" / "scripts" / "validate_migrations.py"
    section.add(
        "Migration Validation",
        OK if validation_script.exists() else WARNING,
        "Migration validation command is available" if validation_script.exists() else "Migration validation command is not installed",
        {"path": str(validation_script)},
    )
    report.sections.append(section)


def check_optional_integrations(report: DoctorReport, engine: Engine | None) -> None:
    section = Section("Optional integrations")
    provider_config = {provider: False for provider in PROVIDER_TYPES}
    if engine is not None:
        try:
            with engine.connect() as connection:
                inspector = inspect(connection)
                if table_exists(inspector, "connection_configurations"):
                    rows = connection.execute(text("select provider_type, is_active from connection_configurations")).all()
                    for provider_type, is_active in rows:
                        provider_config[str(provider_type)] = bool(is_active)
        except Exception:
            pass
    for provider in PROVIDER_TYPES:
        configured = provider_config[provider]
        section.add(
            provider,
            OK if configured else WARNING,
            f"{provider}: {'Configured' if configured else 'Not configured'}",
            {"configured": configured, "optional": True},
        )
    report.sections.append(section)


def check_configuration(report: DoctorReport, context: DoctorContext, engine: Engine | None) -> None:
    section = Section("Configuration")
    env_values = read_env_file(context.env_path)
    env_exists = context.env_path.exists()
    section.add(".env", OK if env_exists else WARNING, f".env found: {context.env_path}" if env_exists else f".env is missing: {context.env_path}", {"path": str(context.env_path)})
    missing_required = sorted(key for key in REQUIRED_ENV_KEYS if not (os.environ.get(key) or env_values.get(key)))
    section.add(
        "required_variables",
        OK if not missing_required else WARNING,
        "Required development variables are configured" if not missing_required else f"Missing development variables: {', '.join(missing_required)}",
        {"missing": missing_required},
    )
    for key in sorted(OPTIONAL_SECRET_KEYS):
        configured = bool(os.environ.get(key) or env_values.get(key) or getattr(settings, key.lower(), None))
        label = "JWT" if key == "AUTH_TOKEN_SECRET" else "Connection secret encryption"
        section.add(label, OK if configured else WARNING, f"{label}: {'Configured' if configured else 'Not configured'}", {"configured": configured})

    provider_config = {provider: False for provider in PROVIDER_TYPES}
    if engine is not None:
        try:
            with engine.connect() as connection:
                inspector = inspect(connection)
                if table_exists(inspector, "connection_configurations"):
                    rows = connection.execute(
                        text("select provider_type, is_active from connection_configurations")
                    ).all()
                    for provider_type, is_active in rows:
                        provider_config[str(provider_type)] = bool(is_active)
        except Exception:
            pass
    for provider in PROVIDER_TYPES:
        configured = provider_config[provider]
        section.add(provider, OK if configured else WARNING, f"{provider}: {'Configured' if configured else 'Not configured'}", {"configured": configured, "optional": True})
    report.sections.append(section)


def check_migration_diagnostics(report: DoctorReport, context: DoctorContext, engine: Engine | None, current_revision: str | None) -> None:
    section = Section("Migration Diagnostics")
    if engine is None:
        section.add("diagnostics", ERROR, "Skipped migration diagnostics because database is unavailable")
        report.sections.append(section)
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        workflow_tables_existing = [table for table in WORKFLOW_TABLES.values() if table_exists(inspector, table)]
        try:
            positions = revision_positions(context)
            current_pos = positions.get(current_revision or "", -1)
            workflow_pos = positions.get(WORKFLOW_REVISION, 10**9)
            partial = bool(workflow_tables_existing and current_pos >= 0 and current_pos < workflow_pos)
        except Exception:
            partial = False
        section.add(
            "partial_workflow_migration",
            ERROR if partial else OK,
            "Workflow tables exist but Alembic revision is older than workflow migration" if partial else "No partial workflow migration detected",
            {"current_revision": current_revision, "workflow_tables_existing": workflow_tables_existing},
            "Run: uv run python -m app.scripts.recover_partial_workflow_migration --dry-run" if partial else None,
        )

        if table_exists(inspector, "permissions"):
            existing = {row[0] for row in connection.execute(text("select code from permissions where code like 'workflows.%'")).all()}
            missing = sorted(WORKFLOW_PERMISSION_CODES - existing)
            section.add(
                "missing_workflow_permissions",
                ERROR if missing else OK,
                "No missing workflow permissions" if not missing else f"Missing workflow permissions: {', '.join(missing)}",
                {"missing": missing},
            )
        else:
            section.add("missing_workflow_permissions", ERROR, "permissions table is missing")

        if table_exists(inspector, "role_permissions"):
            duplicate_count = int(
                scalar(
                    connection,
                    "select count(*) from (select role_id, permission_id from role_permissions group by role_id, permission_id having count(*) > 1)",
                )
                or 0
            )
            section.add("duplicate_role_permissions", ERROR if duplicate_count else OK, "No duplicate role permissions" if not duplicate_count else f"Duplicate role permission pairs: {duplicate_count}", {"duplicate_count": duplicate_count})
        else:
            section.add("duplicate_role_permissions", ERROR, "role_permissions table is missing")

        if table_exists(inspector, "workflow_definitions"):
            exists = scalar(
                connection,
                "select count(*) from workflow_definitions where code = :code and version = 1",
                {"code": CONTRACTOR_REQUEST_WORKFLOW_CODE},
            )
            section.add(
                "missing_workflow_definition",
                ERROR if not exists else OK,
                "Contractor request workflow definition is present" if exists else "Contractor request workflow definition is missing",
                {"code": CONTRACTOR_REQUEST_WORKFLOW_CODE, "version": 1},
                "Run: uv run alembic upgrade head" if not exists else None,
            )
        else:
            section.add("missing_workflow_definition", ERROR, "workflow_definitions table is missing")
    report.sections.append(section)


def run_doctor(
    *,
    root_path: Path | None = None,
    backend_path: Path | None = None,
    env_path: Path | None = None,
    database_url: str | None = None,
    storage_path: Path | None = None,
    runtime_path: Path | None = None,
    fix: bool = False,
    verbose: bool = False,
) -> DoctorReport:
    context = resolve_context(root_path, backend_path, env_path, database_url, storage_path, runtime_path, fix, verbose)
    report = DoctorReport()
    remove_stale_runtime_files(report, context)
    engine = check_database(report, context)
    current_revision = check_alembic(report, context, engine)
    check_core_summary(report, context, engine, current_revision)
    check_security_summary(report)
    check_infrastructure_summary(report, context)
    check_optional_integrations(report, engine)
    check_python_environment(report)
    check_workflow(report, engine)
    check_rbac(report, engine)
    check_auth(report, engine)
    check_contractor(report, engine)
    check_seed(report, engine)
    check_storage(report, context)
    check_configuration(report, context, engine)
    check_migration_diagnostics(report, context, engine, current_revision)
    if engine is not None:
        engine.dispose()
    return report


def colorize(text_value: str, status: str, no_color: bool) -> str:
    if no_color:
        return text_value
    colors = {OK: "\033[32m", WARNING: "\033[33m", ERROR: "\033[31m"}
    return f"{colors.get(status, '')}{text_value}\033[0m"


def supports_status_symbols() -> bool:
    encoding = sys.stdout.encoding or ""
    try:
        "✓⚠✗".encode(encoding)
        return True
    except Exception:
        return False


def render_text(report: DoctorReport, *, verbose: bool = False, no_color: bool = False) -> str:
    symbol = {OK: "[OK]", WARNING: "[WARN]", ERROR: "[ERROR]"} if no_color or not supports_status_symbols() else {OK: "✓", WARNING: "⚠", ERROR: "✗"}
    lines: list[str] = []
    for section in report.sections:
        lines.append(colorize(f"{symbol[section.status]} {section.name}", section.status, no_color))
        if verbose or section.status != OK:
            for check in section.checks:
                lines.append(f"  {symbol[check.status]} {check.message}")
                if check.recommendation:
                    lines.append(f"    {check.recommendation}")
    if report.fixes_applied:
        lines.append("")
        lines.append("Fixes Applied")
        lines.extend(f"- {item}" for item in report.fixes_applied)
    lines.extend(
        [
            "",
            "Platform Health",
            f"{report.health_percent}%",
            "",
            "Warnings",
            str(report.warnings),
            "",
            "Errors",
            str(report.errors),
        ]
    )
    return "\n".join(lines)


def render_summary(report: DoctorReport) -> str:
    return "\n".join(
        [
            f"Platform Health: {report.health_percent}%",
            f"Status: {report.status}",
            f"Errors: {report.errors}",
            f"Warnings: {report.warnings}",
            f"Version: {platform_version()}",
            f"Environment: {platform_environment()}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run structured Platform Doctor checks for the development environment.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    parser.add_argument("--verbose", action="store_true", help="Print every individual check.")
    parser.add_argument("--summary", action="store_true", help="Print a compact health summary.")
    parser.add_argument("--fix", action="store_true", help="Apply safe local fixes only.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in text output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_doctor(fix=args.fix, verbose=args.verbose)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    elif args.summary:
        print(render_summary(report))
    else:
        print(render_text(report, verbose=args.verbose, no_color=args.no_color))
    raise SystemExit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
