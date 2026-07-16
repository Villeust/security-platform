from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DashboardPeriod(BaseModel):
    key: str
    date_from: datetime
    date_to: datetime


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: int | float
    description: str


class DashboardAttentionItem(BaseModel):
    key: str
    label: str
    count: int
    description: str
    severity: str
    target: str


class DashboardRequestItem(BaseModel):
    id: UUID
    request_number: str | None
    title: str
    facility: str | None
    city: str | None
    work_types: list[str]
    contractor: str | None
    status: str
    priority: str | None
    desired_completion_date: datetime | None
    updated_at: datetime


class DashboardStatusDistributionItem(BaseModel):
    status: str
    count: int


class DashboardContractorSummaryItem(BaseModel):
    contractor_id: UUID
    company: str
    active_assignments: int
    in_progress: int
    awaiting_acceptance: int
    overdue: int
    completed: int
    average_completion_hours: float | None
    status: str


class DashboardDeadlineItem(BaseModel):
    request_id: UUID
    request_number: str | None
    title: str
    facility: str | None
    contractor: str | None
    desired_completion_date: datetime
    severity: str


class DashboardActivityItem(BaseModel):
    id: UUID
    title: str
    category: str
    actor: str | None
    entity_type: str
    entity_id: UUID | None
    created_at: datetime


class DashboardNotificationItem(BaseModel):
    id: UUID
    title: str
    message: str
    severity: str
    created_at: datetime


class DashboardNotificationSummary(BaseModel):
    unread_count: int
    items: list[DashboardNotificationItem]


class DashboardServiceStatusItem(BaseModel):
    key: str
    label: str
    status: str
    description: str
    last_check: datetime | None
    target: str | None = None


class DashboardResponse(BaseModel):
    generated_at: datetime
    period: DashboardPeriod
    attention: list[DashboardAttentionItem]
    metrics: list[DashboardMetric]
    request_status_distribution: list[DashboardStatusDistributionItem]
    request_groups: dict[str, list[DashboardRequestItem]]
    upcoming_deadlines: list[DashboardDeadlineItem]
    contractor_summary: list[DashboardContractorSummaryItem]
    recent_activity: list[DashboardActivityItem]
    notifications: DashboardNotificationSummary
    system_status: list[DashboardServiceStatusItem]
