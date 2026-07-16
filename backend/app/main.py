from fastapi import FastAPI, Response

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
from app.services.contractor_request_workflow import register_contractor_request_workflow_adapter


app = FastAPI(title=settings.project_name)
register_contractor_request_workflow_adapter()


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
