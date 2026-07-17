from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from app.services.notifications.errors import NotificationDomainError

REDACTION_MARKER = "[REDACTED]"
SENSITIVE_KEY_PARTS = {
    "password",
    "passphrase",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "session",
    "api_key",
    "client_secret",
    "private_key",
    "encrypted_secrets",
}


def sanitize_payload(
    value,
    *,
    max_depth: int = 6,
    max_items: int = 100,
    max_string_length: int = 1000,
):
    return _sanitize(value, depth=0, max_depth=max_depth, max_items=max_items, max_string_length=max_string_length)


def _sanitize(value, *, depth: int, max_depth: int, max_items: int, max_string_length: int):
    if depth > max_depth:
        raise NotificationDomainError("Notification payload exceeds maximum depth")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, UUID)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value[:max_string_length]
    if isinstance(value, Mapping):
        if len(value) > max_items:
            raise NotificationDomainError("Notification payload contains too many fields")
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise NotificationDomainError("Notification payload keys must be strings")
            if _is_sensitive_key(key):
                result[key] = REDACTION_MARKER
                continue
            result[key] = _sanitize(item, depth=depth + 1, max_depth=max_depth, max_items=max_items, max_string_length=max_string_length)
        return result
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > max_items:
            raise NotificationDomainError("Notification payload contains too many items")
        return [_sanitize(item, depth=depth + 1, max_depth=max_depth, max_items=max_items, max_string_length=max_string_length) for item in value]
    raise NotificationDomainError(f"Unsupported notification payload value: {type(value).__name__}")


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
