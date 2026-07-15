from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.contractor import router as contractor_router
from app.api.v1.health import router as health_router
from app.api.v1.reference_data import router as reference_data_router
from app.api.v1.requests import router as requests_router
from app.core.config import settings


app = FastAPI(title=settings.project_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(reference_data_router, prefix=settings.api_v1_prefix, tags=["reference data"])
app.include_router(requests_router, prefix=settings.api_v1_prefix)
app.include_router(contractor_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)
