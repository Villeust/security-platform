from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.version import platform_version, version_file, version_metadata
from app.main import app
from app.scripts.validate_migrations import MigrationValidationReport


def test_platform_version_source_and_metadata_are_consistent() -> None:
    assert version_file().read_text(encoding="utf-8").strip() == "0.8.0"
    assert platform_version() == "0.8.0"
    metadata = version_metadata(include_build=False)
    assert metadata["name"] == "Security Platform"
    assert metadata["version"] == "0.8.0"
    assert metadata["workflow_engine"] == "v1"


def test_version_endpoint_returns_platform_metadata() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Security Platform"
    assert payload["version"] == "0.8.0"
    assert payload["environment"]
    assert payload["workflow_engine"] == "v1"


def test_version_cli_outputs_expected_banner(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_module("app.scripts.version", run_name="__main__")

    output = capsys.readouterr().out
    assert "Security Platform" in output
    assert "Version 0.8.0" in output
    assert "Workflow Engine v1" in output


def test_production_environment_validation_rejects_unsafe_defaults() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///prod.db",
            BACKEND_CORS_ORIGINS=["https://security.example"],
            AUTH_TOKEN_SECRET="dev-only-change-before-production",
            CONNECTION_SECRETS_KEY="dev-only-change-before-production",
            PUBLIC_BASE_URL="https://security.example",
            HSTS_ENABLED=True,
            ALLOW_DEV_AUTH_HEADERS=False,
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///prod.db",
            BACKEND_CORS_ORIGINS=["https://security.example"],
            AUTH_TOKEN_SECRET="prod-secret-value-123",
            CONNECTION_SECRETS_KEY="prod-key-value-123",
            PUBLIC_BASE_URL="http://security.example",
            HSTS_ENABLED=True,
            ALLOW_DEV_AUTH_HEADERS=False,
        )


def test_production_environment_validation_accepts_safe_configuration() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        DATABASE_URL="sqlite:///prod.db",
        BACKEND_CORS_ORIGINS=["https://security.example"],
        AUTH_TOKEN_SECRET="prod-secret-value-123",
        CONNECTION_SECRETS_KEY="prod-key-value-123",
        PUBLIC_BASE_URL="https://security.example",
        HSTS_ENABLED=True,
        ALLOW_DEV_AUTH_HEADERS=False,
        AUTH_COOKIE_SAMESITE="strict",
        LOG_FORMAT="json",
    )

    assert settings.environment == "production"


def test_startup_and_stop_scripts_include_phase_c_safety_checks() -> None:
    root = Path(__file__).resolve().parents[2]
    start_script = (root / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")
    stop_script = (root / "scripts" / "stop-dev.ps1").read_text(encoding="utf-8")

    assert "Invoke-PlatformDoctor" in start_script
    assert "Wait-Http" in start_script
    assert "Startup Duration" in start_script
    assert "ForceRestart" in start_script
    assert "Test-ProjectProcess" in stop_script
    assert "Command line unavailable: access denied by Windows." in stop_script
    assert "No unrelated processes were terminated" in stop_script


def test_migration_validation_report_json_shape() -> None:
    report = MigrationValidationReport(database_path="validation.db")
    report.add("clean_upgrade_head", "ok", "ok")
    report.add("downgrade_previous_revision", "warning", "not supported everywhere")

    payload = report.to_dict()

    assert payload["status"] == "ok"
    assert payload["warnings"] == 1
    assert payload["errors"] == 0
    assert json.loads(json.dumps(payload))["steps"][0]["name"] == "clean_upgrade_head"
