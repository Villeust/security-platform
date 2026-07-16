from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID, uuid4


CORRELATION_ID_MAX_LENGTH = 64
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def normalize_correlation_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    candidate = value.strip()
    if not candidate or len(candidate) > CORRELATION_ID_MAX_LENGTH or any(char in candidate for char in "\r\n\t"):
        return str(uuid4())
    try:
        return str(UUID(candidate))
    except (TypeError, ValueError):
        return str(uuid4())


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str:
    current = _correlation_id.get()
    if current:
        return current
    generated = str(uuid4())
    _correlation_id.set(generated)
    return generated


def clear_correlation_id() -> None:
    _correlation_id.set(None)
