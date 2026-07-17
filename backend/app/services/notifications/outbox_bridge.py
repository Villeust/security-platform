from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.notifications import NotificationEventStatus
from app.services.notifications.contracts import get_event_contract
from app.services.notifications.service import ingest_event


@dataclass(frozen=True)
class OutboxBridgeResult:
    processed: bool
    reason: str | None = None


def ingest_outbox_event(db: Session, outbox_event, *, event_type_map: dict[str, str] | None = None) -> OutboxBridgeResult:
    """Bridge one outbox-like event into NotificationEvent.

    Transaction ownership stays with the caller. Unsupported events are left
    untouched so a later configured bridge can process them safely.
    """

    mapped_type = (event_type_map or {}).get(outbox_event.event_type)
    if mapped_type is None:
        return OutboxBridgeResult(processed=False, reason="unsupported_event_type")
    contract = get_event_contract(mapped_type)
    if contract is None or not contract.supported:
        return OutboxBridgeResult(processed=False, reason="unsupported_event_contract")
    event = ingest_event(
        db,
        event_type=mapped_type,
        source_type="DomainEventOutbox",
        source_id=outbox_event.id,
        deduplication_key=f"outbox:{outbox_event.id}:{mapped_type}",
        correlation_id=getattr(outbox_event, "correlation_id", None),
        safe_payload=getattr(outbox_event, "payload", {}) or {},
        occurred_at=getattr(outbox_event, "created_at", None),
    )
    outbox_event.status = "PROCESSED"
    outbox_event.processed_at = event.created_at
    event.status = NotificationEventStatus.PROCESSED
    db.flush()
    return OutboxBridgeResult(processed=True)
