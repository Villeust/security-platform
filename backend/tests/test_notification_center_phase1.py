from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin import AdminNotification, AdminNotificationSeverity, AdminNotificationType, AuthSource, Permission, Role, User, UserRole, UserType
from app.models.notifications import (
    NotificationBodyFormat,
    NotificationChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationEventStatus,
    NotificationMessage,
    NotificationPreference,
    NotificationRecipientType,
    NotificationSeverity,
)
from app.models.reference_data import utc_now
from app.models.workflow import DomainEventOutbox
from app.services.notification_service import create_notification
from app.services.notifications.errors import NotificationDomainError, NotificationTemplateImmutableError
from app.services.notifications.legacy_adapter import ingest_legacy_admin_notification
from app.services.notifications.outbox_bridge import ingest_outbox_event
from app.services.notifications.preferences import get_effective_preference, validate_timezone
from app.services.notifications.recipients import ExplicitUserRecipientResolver, ResolvedRecipient, deduplicate_recipients
from app.services.notifications.renderer import render_template
from app.services.notifications.sanitizer import REDACTION_MARKER, sanitize_payload
from app.services.notifications.service import (
    create_messages_for_event,
    create_template,
    create_template_version,
    ingest_event,
    publish_template,
    update_template,
    upsert_preference,
)
from app.services.notifications.url_policy import validate_action_url
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
    with TestClient(app, headers={"X-User-Role": "PLATFORM_ADMIN"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def user(db: Session, role_code: str = "PLATFORM_ADMIN", user_type: UserType = UserType.INTERNAL) -> User:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role is not None
    item = User(
        username=f"user-{uuid4()}",
        email=f"user-{uuid4()}@example.test",
        display_name="Notification User",
        user_type=user_type,
        auth_source=AuthSource.LOCAL,
        is_active=True,
        is_locked=False,
    )
    db.add(item)
    db.flush()
    db.add(UserRole(user_id=item.id, role_id=role.id))
    db.commit()
    db.refresh(item)
    return item


def template(db: Session):
    return create_template(
        db,
        code="TEST_TEMPLATE",
        name="Test {request_number}",
        category="requests",
        subject_template="Request {request_number}",
        body_template="Body {request_number}",
        supported_channels=[NotificationChannel.IN_APP.value],
    )


def test_create_template_and_unique_code_version(db_session: Session) -> None:
    first = template(db_session)
    second = create_template_version(db_session, first.id)
    assert first.version == 1
    assert second.version == 2


def test_published_template_cannot_be_mutated_and_new_version_can_be_created(db_session: Session) -> None:
    item = publish_template(db_session, template(db_session))
    with pytest.raises(NotificationTemplateImmutableError):
        update_template(db_session, item, {"body_template": "Changed"})
    next_version = create_template_version(db_session, item.id)
    assert next_version.version == 2


def test_safe_template_rendering_and_unsafe_placeholders_rejected() -> None:
    assert render_template("Hello {name}", {"name": "World"}, {"name"}) == "Hello World"
    with pytest.raises(NotificationDomainError):
        render_template("Hello {user.password}", {"user.password": "x"})
    with pytest.raises(NotificationDomainError):
        render_template("Hello {__class__}", {"__class__": "x"})
    with pytest.raises(NotificationDomainError):
        render_template("Hello {name}", {}, {"name"})


def test_html_rendering_is_minimally_sanitized(db_session: Session) -> None:
    item = create_template(
        db_session,
        code="HTML_TEMPLATE",
        name="HTML",
        category="security",
        body_template="<b>{title}</b><script>{bad}</script>",
        body_format=NotificationBodyFormat.HTML,
        supported_channels=[NotificationChannel.IN_APP.value],
    )
    event_item = ingest_event(db_session, event_type="EXPLICIT_TEST_EVENT", source_type="test", safe_payload={"title": "Safe", "bad": "x"})
    recipient = user(db_session)
    messages = create_messages_for_event(
        db_session,
        event=event_item,
        template=item,
        resolvers=[ExplicitUserRecipientResolver([ResolvedRecipient(recipient.id, NotificationRecipientType.INTERNAL, email=recipient.email)])],
    )
    assert "<b>Safe</b>" in messages[0].body
    assert "<script>" not in messages[0].body


def test_payload_sanitization_redacts_and_enforces_limits() -> None:
    payload = sanitize_payload({"Password": "secret", "items": (1, "ok"), "id": uuid4()})
    assert payload["Password"] == REDACTION_MARKER
    assert isinstance(payload["items"], list)
    with pytest.raises(NotificationDomainError):
        sanitize_payload({"a": {"b": {"c": {"d": 1}}}}, max_depth=2)
    with pytest.raises(NotificationDomainError):
        sanitize_payload(list(range(4)), max_items=3)
    with pytest.raises(NotificationDomainError):
        sanitize_payload(object())


def test_action_url_policy() -> None:
    assert validate_action_url("/applications/contractor-requests") == "/applications/contractor-requests"
    for url in ("https://example.test/path", "//example.test/path", "javascript:alert(1)", "/other/path", "/admin\\bad"):
        with pytest.raises(NotificationDomainError):
            validate_action_url(url)


def test_recipient_type_invariants_and_deduplication() -> None:
    internal_id = uuid4()
    tenant_id = uuid4()
    with pytest.raises(NotificationDomainError):
        ResolvedRecipient(internal_id, NotificationRecipientType.INTERNAL, tenant_id=tenant_id)
    with pytest.raises(NotificationDomainError):
        ResolvedRecipient(uuid4(), NotificationRecipientType.CONTRACTOR)
    recipient = ResolvedRecipient(internal_id, NotificationRecipientType.INTERNAL)
    assert deduplicate_recipients([recipient, recipient]) == [recipient]


def test_event_message_delivery_idempotency(db_session: Session) -> None:
    item = template(db_session)
    recipient = user(db_session)
    first = ingest_event(db_session, event_type="EXPLICIT_TEST_EVENT", source_type="test", safe_payload={"request_number": "R-1"}, deduplication_key="event:R-1")
    db_session.commit()
    second = ingest_event(db_session, event_type="EXPLICIT_TEST_EVENT", source_type="test", safe_payload={"request_number": "R-1"}, deduplication_key="event:R-1")
    assert second.id == first.id
    resolver = ExplicitUserRecipientResolver([ResolvedRecipient(recipient.id, NotificationRecipientType.INTERNAL, email=recipient.email)])
    first_messages = create_messages_for_event(db_session, event=second, template=item, resolvers=[resolver])
    second_messages = create_messages_for_event(db_session, event=second, template=item, resolvers=[resolver])
    assert second_messages[0].id == first_messages[0].id
    assert db_session.scalar(select(NotificationMessage).where(NotificationMessage.recipient_user_id == recipient.id)).id == first_messages[0].id
    deliveries = db_session.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_message_id == first_messages[0].id)).all()
    assert len(deliveries) == 1


def test_preference_defaults_critical_override_and_timezone(db_session: Session) -> None:
    recipient = user(db_session)
    effective = get_effective_preference(db_session, recipient.id, "requests", NotificationSeverity.INFO)
    assert effective.effective_in_app_enabled is True
    preference = NotificationPreference(user_id=recipient.id, category="security", in_app_enabled=False, email_enabled=False, minimum_severity=NotificationSeverity.INFO, timezone="UTC")
    db_session.add(preference)
    db_session.flush()
    upsert_preference(db_session, preference, {"timezone": "Europe/Moscow"})
    assert validate_timezone("Europe/Moscow") == "Europe/Moscow"
    critical = get_effective_preference(db_session, recipient.id, "security", NotificationSeverity.CRITICAL)
    assert critical.effective_in_app_enabled is True
    assert critical.override_reason == "critical_policy"
    with pytest.raises(NotificationDomainError):
        validate_timezone("Not/AZone")


def test_new_services_do_not_commit_internally(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_commit() -> None:
        raise AssertionError("new notification service committed internally")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    item = create_template(db_session, code="NO_COMMIT", name="No commit", category="test", body_template="Body", supported_channels=[NotificationChannel.IN_APP.value])
    event_item = ingest_event(db_session, event_type="EXPLICIT_TEST_EVENT", source_type="test", safe_payload={})
    assert item.id is not None
    assert event_item.id is not None


def test_legacy_admin_notification_routes_and_no_automatic_generic_dual_write(client: TestClient, db_session: Session) -> None:
    target = user(db_session)
    legacy = create_notification(
        db_session,
        AdminNotificationType.USER_ACCOUNT_LOCKED,
        AdminNotificationSeverity.HIGH,
        "Locked",
        "User locked",
        user_id=target.id,
        commit=True,
    )
    assert db_session.scalar(select(NotificationMessage)) is None
    listed = client.get("/api/v1/admin/notifications")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == str(legacy.id)
    read = client.post(f"/api/v1/admin/notifications/{legacy.id}/read")
    assert read.status_code == 200
    assert read.json()["read_at"] is not None


def test_legacy_adapter_is_opt_in_and_idempotent(db_session: Session) -> None:
    legacy = create_notification(db_session, AdminNotificationType.PASSWORD_EXPIRING, AdminNotificationSeverity.WARNING, "Password", "Expiring")
    assert db_session.scalar(select(NotificationEvent)) is None
    first = ingest_legacy_admin_notification(db_session, legacy)
    second = ingest_legacy_admin_notification(db_session, legacy)
    assert first.id == second.id


def test_permission_seed_idempotent_and_custom_role_assignment_preserved(db_session: Session) -> None:
    custom_role = Role(code="CUSTOM_NOTIFICATION_TEST", name="Custom", is_system=False, is_active=True)
    permission = db_session.scalar(select(Permission).where(Permission.code == "requests.view"))
    assert permission is not None
    db_session.add(custom_role)
    db_session.flush()
    db_session.add(UserRole(user_id=user(db_session).id, role_id=custom_role.id))
    db_session.commit()
    seed_rbac(db_session)
    seed_rbac(db_session)
    codes = set(db_session.scalars(select(Permission.code).where(Permission.code.like("notifications.%"))).all())
    assert "notifications.templates.manage" in codes
    assert db_session.scalar(select(Role).where(Role.code == "CUSTOM_NOTIFICATION_TEST")) is not None


def test_unknown_event_type_is_handled_safely(db_session: Session) -> None:
    event_item = ingest_event(db_session, event_type="UNKNOWN_EVENT", source_type="test", safe_payload={})
    assert event_item.status == NotificationEventStatus.FAILED
    assert event_item.last_error == "Unsupported notification event type"


def test_unsupported_outbox_event_remains_unprocessed(db_session: Session) -> None:
    outbox = DomainEventOutbox(event_type="UNSUPPORTED", aggregate_type="Test", aggregate_id=uuid4(), payload={"safe": True})
    db_session.add(outbox)
    db_session.flush()
    result = ingest_outbox_event(db_session, outbox)
    assert result.processed is False
    assert outbox.status == "PENDING"


def test_controlled_outbox_bridge_ingests_supported_explicit_event(db_session: Session) -> None:
    outbox = DomainEventOutbox(event_type="TEST_OUTBOX", aggregate_type="Test", aggregate_id=uuid4(), payload={"safe": True}, created_at=utc_now())
    db_session.add(outbox)
    db_session.flush()
    result = ingest_outbox_event(db_session, outbox, event_type_map={"TEST_OUTBOX": "EXPLICIT_TEST_EVENT"})
    assert result.processed is True
    assert outbox.status == "PROCESSED"
    assert db_session.scalar(select(NotificationEvent).where(NotificationEvent.source_id == outbox.id)) is not None
