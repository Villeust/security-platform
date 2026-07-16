from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ContractorCompany(BaseModel):
    id: UUID
    name: str
    code: str
    is_primary: bool


class ContractorMeResponse(BaseModel):
    user_id: UUID
    username: str
    display_name: str
    email: str | None
    roles: list[str]
    permissions: list[str]
    primary_contractor_id: UUID | None
    contractors: list[ContractorCompany]


class ContractorDashboardResponse(BaseModel):
    active_requests: int
    assigned_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    latest_requests: list[dict]


class ContractorNotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    created_at: datetime | None = None
