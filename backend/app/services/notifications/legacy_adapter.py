from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin import AdminNotification
from app.models.notifications import NotificationSeverity
from app.services.notifications.service import ingest_event


def ingest_legacy_admin_notification(
    db: Session,
    legacy: AdminNotification,
    *,
    deduplication_key: str | None = None,
):
    """Opt-in compatibility adapter for future producers.

    This function intentionally does not run from existing legacy callers in
    Phase 1 and does not commit. It only ingests an event envelope so later
    phases can explicitly map legacy events without changing admin API behavior.
    """

    key = deduplication_key or f"legacy-admin-notification:{legacy.id}"
    return ingest_event(
        db,
        event_type=legacy.type.value,
        source_type="AdminNotification",
        source_id=legacy.id if isinstance(legacy.id, UUID) else None,
        deduplication_key=key,
        safe_payload={
            "legacy_notification_id": str(legacy.id),
            "type": legacy.type.value,
            "severity": NotificationSeverity[legacy.severity.value].value,
            "user_id": str(legacy.user_id) if legacy.user_id else None,
        },
        occurred_at=legacy.created_at,
    )
