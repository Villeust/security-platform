from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.correlation import get_correlation_id


SENSITIVE_PARTS = ("password", "temporary_password", "token", "secret", "cookie", "authorization", "csrf", "ldap", "adfs", "smtp")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            result[str(key)] = "***" if any(part in lowered for part in SENSITIVE_PARTS) else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


class CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        record.environment = getattr(record, "environment", None) or settings.environment
        record.service = getattr(record, "service", None) or settings.service_name
        if isinstance(record.msg, dict):
            record.msg = redact(record.msg)
        if record.args:
            record.args = redact(record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None) or get_correlation_id(),
            "environment": getattr(record, "environment", settings.environment),
            "service": getattr(record, "service", settings.service_name),
        }
        for key in (
            "request_method",
            "request_path",
            "status_code",
            "duration_ms",
            "actor_id",
            "actor_type",
            "exception_type",
        ):
            value = getattr(record, key, None)
            if value is not None:
                data[key] = value
        if record.exc_info:
            data["exception_type"] = data.get("exception_type") or record.exc_info[0].__name__
        return json.dumps(redact(data), ensure_ascii=False, default=str)


class PrettyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        parts = [
            timestamp,
            record.levelname.ljust(7),
            record.name,
            f"cid={getattr(record, 'correlation_id', '-')}",
            record.getMessage(),
        ]
        if getattr(record, "duration_ms", None) is not None:
            parts.append(f"duration_ms={record.duration_ms}")
        if getattr(record, "status_code", None) is not None:
            parts.append(f"status={record.status_code}")
        return " | ".join(parts)


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationFilter())
    formatter: logging.Formatter
    if settings.log_format.lower() == "json" or settings.environment.lower() in {"production", "prod"}:
        formatter = JsonFormatter()
    else:
        formatter = PrettyFormatter()
    handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[handler], force=True)
