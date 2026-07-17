import re
from urllib.parse import urlsplit

from app.services.notifications.errors import NotificationDomainError

ALLOWED_PREFIXES = ("/applications/", "/workflow/", "/admin/", "/contractor/")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def validate_action_url(action_url: str | None) -> str | None:
    if action_url is None:
        return None
    if not action_url.startswith("/"):
        raise NotificationDomainError("Notification action URL must be an internal path")
    if action_url.startswith("//") or "\\" in action_url or CONTROL_RE.search(action_url):
        raise NotificationDomainError("Notification action URL is not allowed")
    parsed = urlsplit(action_url)
    if parsed.scheme or parsed.netloc or parsed.username or parsed.password:
        raise NotificationDomainError("Notification action URL must not contain an external origin")
    if not any(action_url == prefix[:-1] or action_url.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise NotificationDomainError("Notification action URL prefix is not allowed")
    return action_url
