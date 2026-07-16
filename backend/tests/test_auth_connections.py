from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AdminAuditLog, AdminNotification, AuthSource, AuthSession, ConnectionConfiguration, ConnectionEventLog, Role, User, UserRole, UserType
from app.models.reference_data import utc_now
from app.services.auth_service import create_session, set_auth_cookies
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


def create_local_user(
    db: Session,
    role_code: str | None = "PLATFORM_ADMIN",
    password: str = "LocalPassword123!",
    auth_source: AuthSource = AuthSource.LOCAL,
) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code)) if role_code else None
    if role_code:
        assert role is not None
    password_hash = password_hasher.hash(password) if auth_source == AuthSource.LOCAL else None
    password_expires_at = password_expires_at_from_now() if auth_source == AuthSource.LOCAL else None
    username_prefix = auth_source.value.lower()
    user = User(
        username=f"{username_prefix}-{uuid4()}",
        email=f"{username_prefix}-{uuid4()}@example.test",
        display_name="Local User",
        user_type=UserType.INTERNAL,
        auth_source=auth_source,
        password_hash=password_hash,
        password_expires_at=password_expires_at,
        authentication_enabled=True,
        is_active=True,
        is_locked=False,
    )
    db.add(user)
    db.flush()
    if role is not None:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def login_with_csrf(client: TestClient, user: User, password: str = "LocalPassword123!") -> str:
    response = client.post("/api/v1/auth/login", json={"username": user.username, "password": password, "provider": "LOCAL"})
    assert response.status_code == 200
    csrf = client.cookies.get(settings.auth_csrf_cookie_name)
    assert csrf
    return csrf


def change_password_payload(current: str = "LocalPassword123!", new: str = "NewLocalPassword123!") -> dict[str, str]:
    return {
        "current_password": current,
        "new_password": new,
        "new_password_confirmation": new,
    }


def set_session_cookies(client: TestClient, db: Session, user: User, restricted: bool = False) -> str:
    class DummyClient:
        host = "testclient"

    class DummyRequest:
        client = DummyClient()
        headers = {"user-agent": "pytest"}

    class DummyResponse:
        def __init__(self) -> None:
            self.cookies: dict[str, str] = {}

        def set_cookie(self, name: str, value: str, **_: object) -> None:
            self.cookies[name] = value

    session, access_token, refresh_token, csrf_token = create_session(db, user, DummyRequest(), restricted=restricted)
    db.commit()
    response = DummyResponse()
    set_auth_cookies(response, access_token, refresh_token, csrf_token)
    for name, value in response.cookies.items():
        client.cookies.set(name, value)
    assert db.get(AuthSession, session.id) is not None
    return csrf_token


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
    csrf = login_with_csrf(client, user)
    response = client.post("/api/v1/auth/change-password", headers={"X-CSRF-Token": csrf}, json=change_password_payload())
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["must_change_password"] is False
    db_session.refresh(user)
    assert user.must_change_password is False


def test_successful_temporary_password_change_lifecycle(client: TestClient, db_session: Session) -> None:
    admin = create_local_user(db_session)
    response = client.post(
        "/api/v1/admin/users",
        headers=auth(admin),
        json={
            "username": f"temporary-{uuid4()}",
            "email": f"temporary-{uuid4()}@example.test",
            "display_name": "Temporary User",
            "user_type": "INTERNAL",
            "auth_source": "LOCAL",
            "role_ids": [],
            "contractor_memberships": [],
        },
    )
    assert response.status_code == 201
    data = response.json()
    temporary_password = data["temporary_password"]
    assert temporary_password
    assert data["must_change_password"] is True

    created_user = db_session.get(User, UUID(data["id"]))
    assert created_user is not None
    csrf = login_with_csrf(client, created_user, temporary_password)
    change_response = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json=change_password_payload(temporary_password, "NewLocalPassword123!"),
    )
    assert change_response.status_code == 200
    user = db_session.get(User, UUID(data["id"]))
    assert user is not None
    db_session.refresh(user)
    assert user.must_change_password is False
    assert user.password_expires_at is not None
    assert password_hasher.verify("NewLocalPassword123!", user.password_hash)
    assert not password_hasher.verify(temporary_password, user.password_hash)

    assert client.post("/api/v1/auth/login", json={"username": user.username, "password": temporary_password}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": user.username, "password": "NewLocalPassword123!"}).status_code == 200


def test_change_password_rejects_wrong_current_password(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json=change_password_payload("WrongPassword123!", "NewLocalPassword123!"),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CURRENT_PASSWORD_INVALID"


def test_change_password_rejects_confirmation_mismatch(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={
            "current_password": "LocalPassword123!",
            "new_password": "NewLocalPassword123!",
            "new_password_confirmation": "DifferentPassword123!",
        },
    )
    assert response.status_code == 422
    assert "PASSWORD_CONFIRMATION_MISMATCH" in str(response.json()["detail"])


def test_change_password_rejects_policy_violation(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json=change_password_payload("LocalPassword123!", "Talan7680!"),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "PASSWORD_TOO_SHORT"


def test_change_password_rejects_current_password_reuse(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json=change_password_payload("LocalPassword123!", "LocalPassword123!"),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "PASSWORD_REUSE_NOT_ALLOWED"


def test_restricted_session_can_change_password(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    user.must_change_password = True
    db_session.commit()
    csrf = login_with_csrf(client, user)
    response = client.post("/api/v1/auth/change-password", headers={"X-CSRF-Token": csrf}, json=change_password_payload())
    assert response.status_code == 200


def test_restricted_session_cannot_access_other_protected_endpoints(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    user.must_change_password = True
    db_session.commit()
    assert client.post("/api/v1/auth/login", json={"username": user.username, "password": "LocalPassword123!"}).status_code == 200
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 403
    assert response.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"


def test_change_password_recalculates_expiry_and_resets_flags(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    old_expiry = user.password_expires_at
    user.must_change_password = True
    user.failed_login_attempts = 3
    user.password_expired_at = utc_now()
    user.password_expiry_notified_at = utc_now()
    db_session.commit()
    csrf = login_with_csrf(client, user)
    response = client.post("/api/v1/auth/change-password", headers={"X-CSRF-Token": csrf}, json=change_password_payload())
    assert response.status_code == 200
    db_session.refresh(user)
    assert user.must_change_password is False
    assert user.failed_login_attempts == 0
    assert user.password_expired_at is None
    assert user.password_expiry_notified_at is None
    assert user.password_expires_at is not None
    assert old_expiry is None or user.password_expires_at > old_expiry


def test_change_password_rejects_non_local_user(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session, auth_source=AuthSource.LDAP)
    csrf = set_session_cookies(client, db_session, user)
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json=change_password_payload(),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "LOCAL_PASSWORD_NOT_AVAILABLE"


def test_change_password_requires_csrf(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    login_with_csrf(client, user)
    response = client.post("/api/v1/auth/change-password", json=change_password_payload())
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF_TOKEN_INVALID"


def test_change_password_accepts_valid_csrf(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    response = client.post("/api/v1/auth/change-password", headers={"X-CSRF-Token": csrf}, json=change_password_payload())
    assert response.status_code == 200


def test_password_changed_audit_contains_no_secrets(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    response = client.post("/api/v1/auth/change-password", headers={"X-CSRF-Token": csrf}, json=change_password_payload())
    assert response.status_code == 200
    audit = db_session.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "PASSWORD_CHANGED"))
    assert audit is not None
    assert audit.actor_id == user.id
    assert "LocalPassword123!" not in str(audit.old_data)
    assert "NewLocalPassword123!" not in str(audit.new_data)


def test_logout_invalidates_session(client: TestClient, db_session: Session) -> None:
    user = create_local_user(db_session)
    csrf = login_with_csrf(client, user)
    assert client.get("/api/v1/auth/me").status_code == 200

    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


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
