from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import Permission, Role, RolePermission, User, UserRole, UserType
from app.models.notifications import NotificationRecipientType
from app.services.notifications.errors import NotificationDomainError


@dataclass(frozen=True)
class ResolvedRecipient:
    user_id: UUID
    recipient_type: NotificationRecipientType
    tenant_id: UUID | None = None
    email: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.recipient_type == NotificationRecipientType.INTERNAL and self.tenant_id is not None:
            raise NotificationDomainError("Internal notification recipient cannot have tenant_id")
        if self.recipient_type == NotificationRecipientType.CONTRACTOR and self.tenant_id is None:
            raise NotificationDomainError("Contractor notification recipient requires tenant_id")


class RecipientResolver:
    def resolve(self, db: Session) -> list[ResolvedRecipient]:
        raise NotImplementedError


class ExplicitUserRecipientResolver(RecipientResolver):
    def __init__(self, recipients: list[ResolvedRecipient]) -> None:
        self.recipients = recipients

    def resolve(self, db: Session) -> list[ResolvedRecipient]:
        return self.recipients


class PermissionRecipientResolver(RecipientResolver):
    def __init__(self, permission_code: str) -> None:
        self.permission_code = permission_code

    def resolve(self, db: Session) -> list[ResolvedRecipient]:
        rows = db.scalars(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                Permission.code == self.permission_code,
                Permission.is_active.is_(True),
                Role.is_active.is_(True),
                User.is_active.is_(True),
                User.is_locked.is_(False),
                User.user_type == UserType.INTERNAL,
            )
        ).unique().all()
        return [
            ResolvedRecipient(user_id=user.id, recipient_type=NotificationRecipientType.INTERNAL, email=user.email, reason=f"permission:{self.permission_code}")
            for user in rows
        ]


class PlatformAdminRecipientResolver(PermissionRecipientResolver):
    def __init__(self) -> None:
        super().__init__("notifications.manage")


class SecurityAdminRecipientResolver(RecipientResolver):
    def resolve(self, db: Session) -> list[ResolvedRecipient]:
        rows = db.scalars(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == "SECURITY_ADMIN", Role.is_active.is_(True), User.is_active.is_(True), User.is_locked.is_(False), User.user_type == UserType.INTERNAL)
        ).unique().all()
        return [ResolvedRecipient(user_id=user.id, recipient_type=NotificationRecipientType.INTERNAL, email=user.email, reason="role:SECURITY_ADMIN") for user in rows]


def deduplicate_recipients(recipients: list[ResolvedRecipient]) -> list[ResolvedRecipient]:
    deduped: dict[tuple[UUID, NotificationRecipientType, UUID | None], ResolvedRecipient] = {}
    for recipient in recipients:
        deduped.setdefault((recipient.user_id, recipient.recipient_type, recipient.tenant_id), recipient)
    return list(deduped.values())
