import logging
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.connections import router as connections_router
from app.api.v1.contractor import router as contractor_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.reference_data import router as reference_data_router
from app.api.v1.requests import router as requests_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.workflow_center import router as workflow_center_router
from app.core.config import settings
from app.core.correlation import clear_correlation_id, normalize_correlation_id, set_correlation_id
from app.core.errors import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    integrity_exception_handler,
    sqlalchemy_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.security import apply_security_headers, reject_oversized_request
from app.core.version import platform_version
from app.services.contractor_request_workflow import register_contractor_request_workflow_adapter


configure_logging()
logger = logging.getLogger("app.request")

app = FastAPI(title=settings.project_name, version=platform_version())
register_contractor_request_workflow_adapter()
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)


@app.middleware("http")
async def cors_with_credentials(request, call_next):
    origin = request.headers.get("origin")
    is_allowed_origin = origin in settings.backend_cors_origins
    if request.method == "OPTIONS" and is_allowed_origin and request.headers.get("access-control-request-method"):
        response = Response("OK")
    else:
        response = await call_next(request)
    if is_allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get("access-control-request-headers", "*")
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers["Vary"] = "Origin"
    return response


@app.middleware("http")
async def platform_request_context(request: Request, call_next):
    correlation_id = normalize_correlation_id(request.headers.get(settings.correlation_id_header))
    set_correlation_id(correlation_id)
    started = time.perf_counter()
    response: Response | None = None
    try:
        response = reject_oversized_request(request)
        if response is None:
            response = await call_next(request)
        apply_security_headers(request, response)
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        status_code = response.status_code if response is not None else 500
        if response is not None:
            response.headers[settings.correlation_id_header] = correlation_id
        is_health_poll = request.url.path.endswith("/health") or request.url.path.endswith("/readiness")
        if settings.log_health_requests or not (is_health_poll and status_code < 400):
            level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code in {401, 403} else logging.INFO
            logger.log(
                level,
                "HTTP request completed",
                extra={
                    "request_method": request.method,
                    "request_path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
        clear_correlation_id()


app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(reference_data_router, prefix=settings.api_v1_prefix, tags=["reference data"])
app.include_router(requests_router, prefix=settings.api_v1_prefix)
app.include_router(contractor_router, prefix=settings.api_v1_prefix)
app.include_router(dashboard_router, prefix=settings.api_v1_prefix)
app.include_router(workflows_router, prefix=settings.api_v1_prefix)
app.include_router(workflow_center_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(connections_router, prefix=settings.api_v1_prefix)
