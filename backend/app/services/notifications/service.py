from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.correlation import get_correlation_id
from app.models.notifications import (
    NotificationBodyFormat,
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventStatus,
    NotificationMessage,
    NotificationPreference,
    NotificationSeverity,
    NotificationTemplate,
)
from app.models.reference_data import utc_now
from app.services.audit_service import write_audit
from app.services.notifications.contracts import get_event_contract
from app.services.notifications.errors import NotificationDomainError, NotificationTemplateImmutableError
from app.services.notifications.preferences import get_effective_preference, severity_allowed, validate_timezone
from app.services.notifications.recipients import RecipientResolver, ResolvedRecipient, deduplicate_recipients
from app.services.notifications.renderer import render_body, render_template
from app.services.notifications.sanitizer import sanitize_payload
from app.services.notifications.url_policy import validate_action_url

MUTABLE_TEMPLATE_FIELDS = {"name", "description", "category", "subject_template", "body_template", "body_format", "supported_channels", "default_severity"}


@dataclass(frozen=True)
class RenderedNotification:
    title: str
    body: str


def validate_supported_channels(channels: list[str]) -> list[str]:
    if not channels:
        raise NotificationDomainError("Notification template must support at least one channel")
    allowed = {channel.value for channel in NotificationChannel}
    unsupported = sorted(set(channels) - allowed)
    if unsupported:
        raise NotificationDomainError(f"Unsupported notification channels: {', '.join(unsupported)}")
    return list(dict.fromkeys(channels))


def create_template(
    db: Session,
    *,
    code: str,
    name: str,
    category: str,
    body_template: str,
    supported_channels: list[str],
    subject_template: str | None = None,
    description: str | None = None,
    body_format: NotificationBodyFormat = NotificationBodyFormat.TEXT,
    default_severity: NotificationSeverity = NotificationSeverity.INFO,
    actor_id: UUID | None = None,
) -> NotificationTemplate:
    latest = db.scalar(select(func.max(NotificationTemplate.version)).where(NotificationTemplate.code == code))
    template = NotificationTemplate(
        code=code,
        version=1 if latest is None else latest + 1,
        name=name,
        description=description,
        category=category,
        subject_template=subject_template,
        body_template=body_template,
        body_format=body_format,
        supported_channels=validate_supported_channels(supported_channels),
        default_severity=default_severity,
        is_active=True,
        is_published=False,
    )
    db.add(template)
    db.flush()
    audit_action = "NOTIFICATION_TEMPLATE_CREATED" if template.version == 1 else "NOTIFICATION_TEMPLATE_VERSION_CREATED"
    write_audit(db, audit_action, "NotificationTemplate", template.id, actor_id=actor_id, new_data={"code": code, "version": template.version, "category": category})
    return template


def create_template_version(db: Session, source_template_id: UUID, actor_id: UUID | None = None) -> NotificationTemplate:
    source = get_template_or_raise(db, source_template_id)
    return create_template(
        db,
        code=source.code,
        name=source.name,
        category=source.category,
        body_template=source.body_template,
        supported_channels=list(source.supported_channels),
        subject_template=source.subject_template,
        description=source.description,
        body_format=source.body_format,
        default_severity=source.default_severity,
        actor_id=actor_id,
    )


def publish_template(db: Session, template: NotificationTemplate) -> NotificationTemplate:
    template.is_published = True
    db.flush()
    return template


def update_template(db: Session, template: NotificationTemplate, values: dict, actor_id: UUID | None = None) -> NotificationTemplate:
    if template.is_published and set(values).intersection(MUTABLE_TEMPLATE_FIELDS):
        raise NotificationTemplateImmutableError("Published notification template content is immutable")
    if "supported_channels" in values:
        values["supported_channels"] = validate_supported_channels(values["supported_channels"])
    for field, value in values.items():
        setattr(template, field, value)
    db.flush()
    return template


def deactivate_template(db: Session, template: NotificationTemplate, actor_id: UUID | None = None) -> NotificationTemplate:
    template.is_active = False
    write_audit(db, "NOTIFICATION_TEMPLATE_DEACTIVATED", "NotificationTemplate", template.id, actor_id=actor_id, new_data={"code": template.code, "version": template.version})
    db.flush()
    return template


def get_template_or_raise(db: Session, template_id: UUID) -> NotificationTemplate:
    template = db.get(NotificationTemplate, template_id)
    if template is None:
        raise NotificationDomainError("Notification template not found")
    return template


def render_notification(template: NotificationTemplate, values: dict[str, object], allowed_placeholders: set[str] | None = None) -> RenderedNotification:
    title_template = template.subject_template or template.name
    return RenderedNotification(
        title=render_template(title_template, values, allowed_placeholders),
        body=render_body(template.body_template, values, template.body_format, allowed_placeholders),
    )


def ingest_event(
    db: Session,
    *,
    event_type: str,
    source_type: str,
    safe_payload: dict,
    source_id: UUID | None = None,
    deduplication_key: str | None = None,
    correlation_id: str | None = None,
    tenant_type: str | None = None,
    tenant_id: UUID | None = None,
    occurred_at: datetime | None = None,
    payload_schema_version: int = 1,
) -> NotificationEvent:
    if get_event_contract(event_type) is None:
        event = NotificationEvent(
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            deduplication_key=deduplication_key,
            correlation_id=correlation_id or get_correlation_id(),
            tenant_type=tenant_type,
            tenant_id=tenant_id,
            safe_payload=sanitize_payload(safe_payload),
            payload_schema_version=payload_schema_version,
            occurred_at=occurred_at or utc_now(),
            status=NotificationEventStatus.FAILED,
            last_error="Unsupported notification event type",
        )
        db.add(event)
        db.flush()
        return event
    if deduplication_key:
        existing = db.scalar(select(NotificationEvent).where(NotificationEvent.deduplication_key == deduplication_key))
        if existing is not None:
            return existing
    event = NotificationEvent(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        deduplication_key=deduplication_key,
        correlation_id=correlation_id or get_correlation_id(),
        tenant_type=tenant_type,
        tenant_id=tenant_id,
        safe_payload=sanitize_payload(safe_payload),
        payload_schema_version=payload_schema_version,
        occurred_at=occurred_at or utc_now(),
        status=NotificationEventStatus.PENDING,
    )
    db.add(event)
    db.flush()
    write_audit(db, "NOTIFICATION_EVENT_INGESTED", "NotificationEvent", event.id, new_data={"event_type": event.event_type, "source_type": event.source_type, "deduplication_key": event.deduplication_key})
    return event


def create_messages_for_event(
    db: Session,
    *,
    event: NotificationEvent,
    template: NotificationTemplate | None,
    resolvers: list[RecipientResolver],
    render_values: dict[str, object] | None = None,
    title: str | None = None,
    body: str | None = None,
    category: str | None = None,
    severity: NotificationSeverity | None = None,
    action_url: str | None = None,
    action_label: str | None = None,
    channels: list[NotificationChannel] | None = None,
) -> list[NotificationMessage]:
    recipients = deduplicate_recipients([recipient for resolver in resolvers for recipient in resolver.resolve(db)])
    if template is not None:
        rendered = render_notification(template, render_values or event.safe_payload)
        title = rendered.title
        body = rendered.body
        category = category or template.category
        severity = severity or template.default_severity
    if not title or not body or not category:
        raise NotificationDomainError("Notification message title, body and category are required")
    severity = severity or NotificationSeverity.INFO
    action_url = validate_action_url(action_url)
    messages: list[NotificationMessage] = []
    for recipient in recipients:
        preference = get_effective_preference(db, recipient.user_id, category, severity)
        if not preference.effective_in_app_enabled or not severity_allowed(severity, preference.minimum_severity):
            continue
        deduplication_key = message_deduplication_key(event.id, recipient, template)
        existing = db.scalar(select(NotificationMessage).where(NotificationMessage.message_deduplication_key == deduplication_key))
        if existing is not None:
            messages.append(existing)
            continue
        message = NotificationMessage(
            notification_event_id=event.id,
            template_id=template.id if template else None,
            message_deduplication_key=deduplication_key,
            recipient_user_id=recipient.user_id,
            recipient_type=recipient.recipient_type,
            tenant_id=recipient.tenant_id,
            category=category,
            severity=severity,
            title=title,
            body=body,
            action_url=action_url,
            action_label=action_label,
        )
        db.add(message)
        db.flush()
        write_audit(db, "NOTIFICATION_MESSAGE_CREATED", "NotificationMessage", message.id, new_data={"category": category, "severity": severity.value, "recipient_type": recipient.recipient_type.value})
        create_delivery_records(db, message=message, recipient=recipient, channels=channels or [NotificationChannel.IN_APP])
        messages.append(message)
    return messages


def create_delivery_records(db: Session, *, message: NotificationMessage, recipient: ResolvedRecipient, channels: list[NotificationChannel]) -> list[NotificationDelivery]:
    records: list[NotificationDelivery] = []
    for channel in channels:
        if channel == NotificationChannel.EMAIL and not recipient.email:
            continue
        recipient_address = recipient.email if channel == NotificationChannel.EMAIL else None
        deduplication_key = delivery_deduplication_key(message.id, channel, recipient_address)
        existing = db.scalar(select(NotificationDelivery).where(NotificationDelivery.delivery_deduplication_key == deduplication_key))
        if existing is not None:
            records.append(existing)
            continue
        delivery = NotificationDelivery(
            notification_message_id=message.id,
            delivery_deduplication_key=deduplication_key,
            channel=channel,
            recipient_address=recipient_address,
            status=NotificationDeliveryStatus.PENDING,
            correlation_id=message.event.correlation_id,
        )
        db.add(delivery)
        db.flush()
        records.append(delivery)
    return records


def upsert_preference(db: Session, preference: NotificationPreference, values: dict, actor_id: UUID | None = None) -> NotificationPreference:
    if "timezone" in values:
        validate_timezone(values["timezone"])
    for field, value in values.items():
        setattr(preference, field, value)
    write_audit(db, "NOTIFICATION_PREFERENCE_CHANGED", "NotificationPreference", preference.id, actor_id=actor_id, new_data={"user_id": str(preference.user_id), "category": preference.category})
    db.flush()
    return preference


def message_deduplication_key(event_id: UUID, recipient: ResolvedRecipient, template: NotificationTemplate | None) -> str:
    template_part = f"{template.id}:{template.version}" if template else "no-template"
    return f"{event_id}:{recipient.user_id}:{recipient.recipient_type.value}:{recipient.tenant_id or 'none'}:{template_part}"


def delivery_deduplication_key(message_id: UUID, channel: NotificationChannel, recipient_address: str | None) -> str:
    return f"{message_id}:{channel.value}:{recipient_address or 'in_app'}"
