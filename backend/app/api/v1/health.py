from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.readiness import readiness_checks
from app.core.version import version_metadata
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "contractor-requests-api"}


@router.get("/readiness")
def readiness(response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    report = readiness_checks(db)
    if report["status"] != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report


@router.get("/version")
def version() -> dict[str, str | None]:
    return version_metadata()
