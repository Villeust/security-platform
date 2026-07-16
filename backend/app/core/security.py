from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.correlation import get_correlation_id
from app.core.errors import AppErrorCode, error_payload


AUTH_CACHE_PREFIXES = ("/api/v1/auth", "/api/v1/admin")


def is_production() -> bool:
    return settings.environment.lower() in {"production", "prod"}


def content_security_policy() -> str:
    if is_production():
        return "; ".join(
            [
                "default-src 'self'",
                "base-uri 'self'",
                "frame-ancestors 'none'",
                "object-src 'none'",
                "img-src 'self' data:",
                "style-src 'self' 'unsafe-inline'",
                "script-src 'self'",
                "connect-src 'self'",
            ]
        )
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "frame-ancestors 'self'",
            "object-src 'none'",
            "img-src 'self' data:",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*",
        ]
    )


def apply_security_headers(request: Request, response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY" if is_production() else "SAMEORIGIN")
    response.headers.setdefault("Content-Security-Policy", content_security_policy())
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if request.url.path.startswith(AUTH_CACHE_PREFIXES) or "/download" in request.url.path:
        response.headers.setdefault("Cache-Control", "no-store")
    if is_production() and settings.hsts_enabled:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def request_size_limit(request: Request) -> int:
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        return min(settings.max_request_body_bytes, settings.max_multipart_body_bytes)
    if "application/json" in content_type or content_type.endswith("+json"):
        return min(settings.max_request_body_bytes, settings.max_json_body_bytes)
    return settings.max_request_body_bytes


def reject_oversized_request(request: Request) -> JSONResponse | None:
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        return None
    try:
        length = int(raw_length)
    except ValueError:
        length = settings.max_request_body_bytes + 1
    if length <= request_size_limit(request):
        return None
    response = JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content=error_payload(request, AppErrorCode.PAYLOAD_TOO_LARGE, legacy_detail="Payload too large"),
    )
    response.headers[settings.correlation_id_header] = get_correlation_id()
    return response


def safe_download_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
