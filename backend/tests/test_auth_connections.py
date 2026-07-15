from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AdminNotification, AuthSource, ConnectionConfiguration, ConnectionEventLog, Role, User, UserRole, UserType
from app.services.password_service import password_expires_at_from_now, password_hasher
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


def create_local_user(db: Session, role_code: str = "PLATFORM_ADMIN", password: str = "LocalPassword123!") -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    user = User(
        username=f"local-{uuid4()}",
        email=f"local-{uuid4()}@example.test",
        display_name="Local User",
        user_type=UserType.INTERNAL,
        auth_source=AuthSource.LOCAL,
        password_hash=password_hasher.hash(password),
        password_expires_at=password_expires_at_from_now(),
        authentication_enabled=True,
        is_active=True,
        is_locked=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def test_local_login_sets_session_cookies(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    response = client.post("/api/v1/auth/login", json={"username": user.username, "password": "LocalPassword123!", "provider": "LOCAL"})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == user.username
    assert settings.auth_access_cookie_name in response.cookies
    assert settings.auth_refresh_cookie_name in response.cookies


def test_change_password_clears_must_change_password(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    user.must_change_password = True
    db_session.commit()
    assert client.post("/api/v1/auth/login", json={"username": user.username, "password": "LocalPassword123!"}).status_code == 200
    response = client.post("/api/v1/auth/change-password", json={"current_password": "LocalPassword123!", "new_password": "NewLocalPassword123!"})
    assert response.status_code == 200
    db_session.refresh(user)
    assert user.must_change_password is False


def test_repeated_failed_login_locks_user(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    for _ in range(settings.max_failed_login_attempts):
        response = client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrong"})
        assert response.status_code == 401
    db_session.refresh(user)
    assert user.is_locked is True
    assert db_session.scalar(select(AdminNotification).where(AdminNotification.user_id == user.id)) is not None


def test_non_local_provider_does_not_fake_success(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "user", "password": "pass", "provider": "LDAP"})
    assert response.status_code == 400
    assert response.json()["detail"] == "PROVIDER_NOT_CONFIGURED"


def test_connection_secret_is_masked_and_event_is_logged(client: TestClient, db_session: Session) -> None:
    admin = create_local_user(db_session)
    response = client.put(
        "/api/v1/admin/connections/smtp",
        headers=auth(admin),
        json={"name": "SMTP", "host": "smtp.example.test", "port": 587, "username": "mailer", "password": "SecretPassword123!", "from_email": "security@example.test"},
    )
    assert response.status_code == 200
    assert response.json()["configuration_json"].get("password") in {None, "***"}
    stored = db_session.scalar(select(ConnectionConfiguration).where(ConnectionConfiguration.provider_type == "SMTP"))
    assert stored is not None
    assert "SecretPassword123!" not in str(stored.encrypted_secrets)
    assert db_session.scalar(select(ConnectionEventLog).where(ConnectionEventLog.event_type == "CONFIG_UPDATED")) is not None


def test_connection_test_for_unconfigured_provider_fails_safely(client: TestClient, db_session: Session) -> None:
    admin = create_local_user(db_session)
    response = client.post("/api/v1/admin/connections/ldap/test", headers=auth(admin))
    assert response.status_code == 200
    assert response.json()["status"] in {"FAILED", "not_configured"}
    assert response.json()["message"]
