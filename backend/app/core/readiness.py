from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.version import platform_version, version_metadata
from app.models.admin import Permission, Role
from app.services.contractor_request_workflow import CONTRACTOR_REQUEST_ENTITY_TYPE
from app.services.rbac_service import seed_rbac
from app.services.workflow_adapters import workflow_adapters


def _backend_path() -> Path:
    return Path(__file__).resolve().parents[2]


def _alembic_head() -> str | None:
    backend = _backend_path()
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("prepend_sys_path", str(backend))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    heads = ScriptDirectory.from_config(config).get_heads()
    return heads[0] if len(heads) == 1 else None


def _storage_ready() -> bool:
    path = Path(settings.storage_root)
    if not path.is_absolute():
        path = _backend_path() / path
    return path.exists() and path.is_dir()


def readiness_checks(db: Session) -> dict[str, Any]:
    checks: dict[str, str] = {}
    details: dict[str, Any] = version_metadata(include_build=False)

    try:
        db.execute(text("select 1")).scalar()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        current = MigrationContext.configure(db.connection()).get_current_revision()
        head = _alembic_head()
        checks["alembic_revision"] = "ok" if current and head and current == head else "error"
        details["alembic_current"] = current
        details["alembic_head"] = head
    except Exception:
        checks["alembic_revision"] = "error"

    try:
        if workflow_adapters.get(CONTRACTOR_REQUEST_ENTITY_TYPE) is None:
            checks["workflow_registry"] = "error"
        else:
            checks["workflow_registry"] = "ok"
    except Exception:
        checks["workflow_registry"] = "error"

    try:
        seed_rbac(db)
        role_count = len(db.scalars(select(Role.id)).all())
        permission_count = len(db.scalars(select(Permission.id)).all())
        checks["rbac"] = "ok" if role_count > 0 and permission_count > 0 else "error"
    except Exception:
        db.rollback()
        checks["rbac"] = "error"

    checks["storage"] = "ok" if _storage_ready() else "error"
    checks["platform_version"] = "ok" if details["version"] else "error"
    status = "ready" if all(value == "ok" for value in checks.values()) else "not_ready"
    return {"status": status, "checks": checks, **details}
