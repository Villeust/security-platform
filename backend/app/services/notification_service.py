from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import AdminNotification, AdminNotificationSeverity, AdminNotificationType
from app.models.reference_data import utc_now
from app.services.audit_service import write_audit


def create_notification(
    db: Session,
    notification_type: AdminNotificationType,
    severity: AdminNotificationSeverity,
    title: str,
    message: str,
    user_id: UUID | None = None,
    details: dict | None = None,
    commit: bool = False,
) -> AdminNotification:
    notification = AdminNotification(
        type=notification_type,
        severity=severity,
        user_id=user_id,
        title=title,
        message=message,
        details=details,
    )
    db.add(notification)
    db.flush()
    write_audit(db, "ADMIN_NOTIFICATION_CREATED", "AdminNotification", notification.id, new_data={"type": notification_type.value, "severity": severity.value})
    if commit:
        db.commit()
        db.refresh(notification)
    return notification


def list_notifications(
    db: Session,
    notification_type: AdminNotificationType | None = None,
    severity: AdminNotificationSeverity | None = None,
    is_read: bool | None = None,
    is_resolved: bool | None = None,
    user_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AdminNotification]:
    query = select(AdminNotification)
    if notification_type:
        query = query.where(AdminNotification.type == notification_type)
    if severity:
        query = query.where(AdminNotification.severity == severity)
    if is_read is not None:
        query = query.where(AdminNotification.read_at.is_not(None) if is_read else AdminNotification.read_at.is_(None))
    if is_resolved is not None:
        query = query.where(AdminNotification.is_resolved == is_resolved)
    if user_id:
        query = query.where(AdminNotification.user_id == user_id)
    if created_from:
        query = query.where(AdminNotification.created_at >= created_from)
    if created_to:
        query = query.where(AdminNotification.created_at <= created_to)
    return list(db.scalars(query.order_by(AdminNotification.created_at.desc()).offset(skip).limit(limit)).all())


def mark_read(db: Session, notification: AdminNotification, actor_id: UUID | None) -> AdminNotification:
    notification.read_at = notification.read_at or utc_now()
    notification.read_by_id = notification.read_by_id or actor_id
    db.commit()
    db.refresh(notification)
    return notification


def resolve_notification(db: Session, notification: AdminNotification, actor_id: UUID | None) -> AdminNotification:
    notification.is_resolved = True
    notification.resolved_at = utc_now()
    notification.resolved_by_id = actor_id
    write_audit(db, "ADMIN_NOTIFICATION_RESOLVED", "AdminNotification", notification.id, actor_id=actor_id)
    db.commit()
    db.refresh(notification)
    return notification
