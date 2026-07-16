from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.correlation import get_correlation_id

logger = logging.getLogger("app.errors")


class AppErrorCode(StrEnum):
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    CONFLICT = "CONFLICT"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"
    DATABASE_CONFLICT = "DATABASE_CONFLICT"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    NOT_FOUND = "RESOURCE_NOT_FOUND"
    PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    RATE_LIMITED = "RATE_LIMITED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    VALIDATION_ERROR = "VALIDATION_ERROR"


SAFE_MESSAGES: dict[AppErrorCode, str] = {
    AppErrorCode.AUTHENTICATION_REQUIRED: "Требуется аутентификация.",
    AppErrorCode.AUTHORIZATION_DENIED: "Недостаточно прав для выполнения операции.",
    AppErrorCode.BUSINESS_RULE_VIOLATION: "Операция не может быть выполнена для текущего состояния данных.",
    AppErrorCode.CONFLICT: "Конфликт данных. Обновите страницу и повторите действие.",
    AppErrorCode.CSRF_TOKEN_INVALID: "Сессия безопасности устарела. Обновите страницу и повторите действие.",
    AppErrorCode.DATABASE_CONFLICT: "Конфликт данных. Проверьте уникальность и связи записей.",
    AppErrorCode.INTERNAL_SERVER_ERROR: "Внутренняя ошибка сервера. Обратитесь к администратору.",
    AppErrorCode.NOT_FOUND: "Запрошенный ресурс не найден.",
    AppErrorCode.PASSWORD_CHANGE_REQUIRED: "Необходимо сменить пароль.",
    AppErrorCode.PAYLOAD_TOO_LARGE: "Размер запроса превышает допустимый лимит.",
    AppErrorCode.PROVIDER_NOT_CONFIGURED: "Провайдер не настроен.",
    AppErrorCode.RATE_LIMITED: "Слишком много запросов. Повторите позже.",
    AppErrorCode.UNSUPPORTED_MEDIA_TYPE: "Неподдерживаемый тип содержимого.",
    AppErrorCode.VALIDATION_ERROR: "Проверьте корректность заполнения полей.",
}


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: AppErrorCode,
        message: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=code.value, headers=headers)
        self.code = code
        self.message = message or SAFE_MESSAGES[code]
        self.details = details


def code_for_http_exception(exc: HTTPException) -> AppErrorCode:
    detail = exc.detail if isinstance(exc.detail, str) else None
    if detail == AppErrorCode.CSRF_TOKEN_INVALID.value:
        return AppErrorCode.CSRF_TOKEN_INVALID
    if detail == AppErrorCode.PASSWORD_CHANGE_REQUIRED.value:
        return AppErrorCode.PASSWORD_CHANGE_REQUIRED
    if detail == AppErrorCode.PROVIDER_NOT_CONFIGURED.value:
        return AppErrorCode.PROVIDER_NOT_CONFIGURED
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return AppErrorCode.AUTHENTICATION_REQUIRED
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return AppErrorCode.AUTHORIZATION_DENIED
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        return AppErrorCode.NOT_FOUND
    if exc.status_code == status.HTTP_409_CONFLICT:
        return AppErrorCode.CONFLICT
    if exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        return AppErrorCode.PAYLOAD_TOO_LARGE
    if exc.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE:
        return AppErrorCode.UNSUPPORTED_MEDIA_TYPE
    if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return AppErrorCode.VALIDATION_ERROR
    if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return AppErrorCode.RATE_LIMITED
    return AppErrorCode.BUSINESS_RULE_VIOLATION if 400 <= exc.status_code < 500 else AppErrorCode.INTERNAL_SERVER_ERROR


def safe_details(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [safe_details(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in ("password", "token", "secret", "cookie", "authorization", "csrf")):
                result[str(key)] = "***"
            else:
                result[str(key)] = safe_details(item)
        return result
    return str(value)


def error_payload(request: Request, code: AppErrorCode, message: str | None = None, details: Any = None, legacy_detail: Any = None) -> dict[str, Any]:
    payload = {
        "error": {
            "code": code.value,
            "message": message or SAFE_MESSAGES[code],
            "details": safe_details(details),
        },
        "correlation_id": get_correlation_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
    }
    if legacy_detail is not None:
        payload["detail"] = safe_details(legacy_detail)
    return payload


def error_response(
    request: Request,
    status_code: int,
    code: AppErrorCode,
    message: str | None = None,
    details: Any = None,
    legacy_detail: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=error_payload(request, code, message, details, legacy_detail),
        headers=headers,
    )
    response.headers["X-Correlation-ID"] = get_correlation_id()
    return response


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error("Application exception", extra={"request_path": request.url.path, "status_code": exc.status_code, "exception_type": type(exc).__name__})
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details, exc.detail, exc.headers)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = code_for_http_exception(exc)
    message = SAFE_MESSAGES[code]
    details = exc.detail if not isinstance(exc.detail, str) or exc.detail != code.value else None
    return error_response(request, exc.status_code, code, message, details, exc.detail, exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = exc.errors()
    return error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        AppErrorCode.VALIDATION_ERROR,
        details=details,
        legacy_detail=details,
    )


async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("Database integrity conflict", extra={"request_path": request.url.path, "status_code": status.HTTP_409_CONFLICT, "exception_type": type(exc).__name__})
    return error_response(request, status.HTTP_409_CONFLICT, AppErrorCode.DATABASE_CONFLICT, legacy_detail="Database constraint conflict")


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database error", extra={"request_path": request.url.path, "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR, "exception_type": type(exc).__name__}, exc_info=exc)
    return error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, AppErrorCode.INTERNAL_SERVER_ERROR)


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unexpected application error", extra={"request_path": request.url.path, "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR, "exception_type": type(exc).__name__}, exc_info=exc)
    return error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, AppErrorCode.INTERNAL_SERVER_ERROR)
