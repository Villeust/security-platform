from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin import AdminAuditLog

SYSTEM_ADMIN_STUB = "SYSTEM_ADMIN_STUB"


def write_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    old_data: dict | None = None,
    new_data: dict | None = None,
    actor_id: UUID | None = None,
    actor_type: str = SYSTEM_ADMIN_STUB,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AdminAuditLog:
    log = AdminAuditLog(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    return log
