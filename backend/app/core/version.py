from __future__ import annotations

import importlib.metadata
import subprocess
from pathlib import Path


PLATFORM_NAME = "Security Platform"
WORKFLOW_ENGINE_VERSION = "v1"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def version_file() -> Path:
    return project_root() / "VERSION"


def platform_environment() -> str:
    from app.core.config import settings

    return settings.environment


def platform_version() -> str:
    path = version_file()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    try:
        return importlib.metadata.version("contractor-requests-backend")
    except importlib.metadata.PackageNotFoundError:
        return "0.8.0"


def git_short_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root(),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def version_metadata(include_build: bool = True) -> dict[str, str | None]:
    data: dict[str, str | None] = {
        "name": PLATFORM_NAME,
        "version": platform_version(),
        "environment": platform_environment(),
        "workflow_engine": WORKFLOW_ENGINE_VERSION,
    }
    if include_build:
        data["build"] = git_short_hash()
    return data
