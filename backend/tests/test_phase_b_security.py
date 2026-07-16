from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.responses import Response

from app.core.config import Settings, settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AuthSource, User, UserType
from app.services.attachment_service import attachment_download_response, validate_original_filename
from app.services.auth_service import clear_auth_cookies, create_session, set_auth_cookies
from app.services.password_service import password_hasher
from app.services.rbac_service import seed_rbac


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as session:
        seed_rbac(session)
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_local_user(db: Session) -> User:
    user = User(
        username=f"security-{uuid4()}",
        display_name="Security User",
        user_type=UserType.INTERNAL,
        auth_source=AuthSource.LOCAL,
        is_active=True,
        is_locked=False,
        password_hash=password_hasher.hash("LocalPassword123!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def csrf_dependency_names(route: APIRoute) -> set[str]:
    names: set[str] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        if dependency.call is not None:
            names.add(getattr(dependency.call, "__name__", ""))
        stack.extend(dependency.dependencies)
    return names


def mutation_routes_missing_csrf(routes) -> list[str]:
    exemptions = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
    }
    missing: list[str] = []
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        methods = set(route.methods or set())
        if not methods.intersection({"POST", "PUT", "PATCH", "DELETE"}):
            continue
        if route.path in exemptions:
            continue
        if "require_csrf" not in csrf_dependency_names(route):
            missing.append(route.path)
    return sorted(missing)


def test_development_security_headers_and_swagger(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "hsts_enabled", False)

    response = client.get("/api/v1/health")
    docs = client.get("/docs")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "cdn.jsdelivr.net" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers
    assert docs.status_code == 200


def test_production_security_headers(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "hsts_enabled", True)

    response = client.get("/api/v1/health")

    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_hsts_absent_when_production_https_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "hsts_enabled", False)

    response = client.get("/api/v1/health")

    assert "Strict-Transport-Security" not in response.headers


def test_cors_approved_and_rejected_origin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "backend_cors_origins", ["http://127.0.0.1:3000"])

    approved = client.options(
        "/api/v1/health",
        headers={"Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "GET"},
    )
    rejected = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert approved.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:3000"
    assert approved.headers["Access-Control-Allow-Credentials"] == "true"
    assert "Access-Control-Allow-Origin" not in rejected.headers


def test_cors_malformed_and_wildcard_configuration_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, BACKEND_CORS_ORIGINS="not-an-origin")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, BACKEND_CORS_ORIGINS="*")


def test_production_missing_origins_and_insecure_secret_fail_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///prod.db",
            BACKEND_CORS_ORIGINS=[],
            AUTH_TOKEN_SECRET="prod-secret",
            CONNECTION_SECRETS_KEY="prod-connection-secret",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///prod.db",
            BACKEND_CORS_ORIGINS=["https://security.example"],
            AUTH_TOKEN_SECRET="secret",
            CONNECTION_SECRETS_KEY="prod-connection-secret",
        )


def test_development_and_production_cookie_flags(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = create_local_user(db_session)
    session, access_token, refresh_token, csrf_token = create_session(db_session, user, SimpleNamespace(client=None, headers={}))

    dev_response = Response()
    monkeypatch.setattr(settings, "environment", "development")
    set_auth_cookies(dev_response, access_token, refresh_token, csrf_token)
    dev_headers = dev_response.headers.getlist("set-cookie")
    assert any(settings.auth_access_cookie_name in item and "HttpOnly" in item and "SameSite=lax" in item and "Path=/" in item for item in dev_headers)
    assert all("Secure" not in item for item in dev_headers)

    prod_response = Response()
    monkeypatch.setattr(settings, "environment", "production")
    set_auth_cookies(prod_response, access_token, refresh_token, csrf_token)
    prod_headers = prod_response.headers.getlist("set-cookie")
    assert all("Secure" in item for item in prod_headers)
    assert any(settings.auth_csrf_cookie_name in item and "HttpOnly" not in item for item in prod_headers)
    assert session


def test_logout_cookie_deletion_matches_creation_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    response = Response()

    clear_auth_cookies(response)

    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 3
    assert all("Max-Age=0" in item and "Path=/" in item and "SameSite=lax" in item and "Secure" in item for item in headers)


def test_csrf_mutation_inventory_passes_and_helpers_detect_missing_or_exemptions() -> None:
    assert mutation_routes_missing_csrf(app.routes) == []

    router = APIRouter()

    @router.post("/unsafe")
    def unsafe() -> dict[str, str]:
        return {"ok": "no"}

    unsafe_route = next(route for route in router.routes if isinstance(route, APIRoute))
    assert "require_csrf" not in csrf_dependency_names(unsafe_route)
    assert "/api/v1/auth/login" not in mutation_routes_missing_csrf(app.routes)


def test_oversized_json_returns_413_with_standard_envelope(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_json_body_bytes", 16)
    correlation_id = str(uuid4())

    response = client.post("/api/v1/auth/login", headers={"X-Correlation-ID": correlation_id}, json={"username": "u" * 100, "password": "p"})

    assert response.status_code == 413
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert response.json()["correlation_id"] == correlation_id


def test_oversized_multipart_returns_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_multipart_body_bytes", 32)

    response = client.post(
        "/api/v1/requests/00000000-0000-0000-0000-000000000000/attachments",
        headers={"X-User-Role": "PLATFORM_ADMIN"},
        files={"file": ("safe.txt", b"x" * 256, "text/plain")},
        data={"category": "GENERAL", "visibility": "INTERNAL"},
    )

    assert response.status_code == 413


def test_pagination_sort_and_search_validation(client: TestClient) -> None:
    headers = {"X-User-Role": "PLATFORM_ADMIN"}

    negative_skip = client.get("/api/v1/requests", headers=headers, params={"skip": -1})
    invalid_sort = client.get("/api/v1/requests", headers=headers, params={"sort_by": "raw_sql"})
    invalid_direction = client.get("/api/v1/requests", headers=headers, params={"sort_order": "sideways"})
    long_search = client.get("/api/v1/requests", headers=headers, params={"search": "x" * (settings.max_search_length + 1)})

    assert negative_skip.status_code == 422
    assert invalid_sort.status_code == 422
    assert invalid_direction.status_code == 422
    assert long_search.status_code == 422


def test_safe_attachment_filename_and_download_headers(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path))
    stored = tmp_path / "requests" / "one" / "file.txt"
    stored.parent.mkdir(parents=True)
    stored.write_text("hello", encoding="utf-8")

    assert validate_original_filename("report.txt") == ("report.txt", "txt")
    with pytest.raises(Exception):
        validate_original_filename("bad\r\nname.txt")

    response = attachment_download_response(
        SimpleNamespace(storage_path="requests/one/file.txt", mime_type="text/plain", original_filename="safe.txt")
    )

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "safe.txt" in response.headers["content-disposition"]
    assert str(tmp_path) not in response.headers["content-disposition"]
