from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notifications import NotificationDigestMode, NotificationPreference, NotificationSeverity
from app.services.notifications.errors import NotificationDomainError

SEVERITY_ORDER = {
    NotificationSeverity.INFO: 10,
    NotificationSeverity.SUCCESS: 20,
    NotificationSeverity.WARNING: 30,
    NotificationSeverity.HIGH: 40,
    NotificationSeverity.CRITICAL: 50,
}
CRITICAL_CATEGORIES = {"security", "platform_health", "auth"}


@dataclass(frozen=True)
class PlatformPreferenceDefault:
    in_app_enabled: bool = True
    email_enabled: bool = False
    minimum_severity: NotificationSeverity = NotificationSeverity.INFO
    timezone: str = "UTC"
    digest_mode: NotificationDigestMode = NotificationDigestMode.IMMEDIATE


@dataclass(frozen=True)
class EffectivePreference:
    configured_preference: NotificationPreference | None
    effective_in_app_enabled: bool
    effective_email_enabled: bool
    minimum_severity: NotificationSeverity
    override_reason: str | None = None


def validate_timezone(timezone: str) -> str:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise NotificationDomainError("Notification preference timezone must be a valid IANA identifier") from exc
    return timezone


def get_effective_preference(db: Session, user_id, category: str, severity: NotificationSeverity) -> EffectivePreference:
    configured = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id, NotificationPreference.category == category))
    default = PlatformPreferenceDefault()
    in_app_enabled = configured.in_app_enabled if configured else default.in_app_enabled
    email_enabled = configured.email_enabled if configured else default.email_enabled
    minimum = configured.minimum_severity if configured else default.minimum_severity
    override_reason = None
    if severity == NotificationSeverity.CRITICAL or category in CRITICAL_CATEGORIES:
        in_app_enabled = True
        override_reason = "critical_policy"
    return EffectivePreference(configured, in_app_enabled, email_enabled, minimum, override_reason)


def severity_allowed(severity: NotificationSeverity, minimum: NotificationSeverity) -> bool:
    return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[minimum]
