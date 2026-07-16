from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_permissions, require_permission
from app.db.session import get_db
from app.models.admin import User
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse, summary="Get security operations dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard.view")),
    permissions: set[str] = Depends(get_current_permissions),
    period: str = Query(default="7d", pattern="^(today|7d|30d|month)$"),
    recent_limit: int = Query(default=8, ge=1, le=20),
) -> DashboardResponse:
    return build_dashboard(db, user, permissions, period, recent_limit)
