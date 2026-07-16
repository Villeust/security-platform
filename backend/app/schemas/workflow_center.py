from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WorkflowMetric(BaseModel):
    key: str
    label: str
    value: int | float | str
    tone: str = "healthy"
    target: str | None = None


class WorkflowDashboardActivity(BaseModel):
    id: UUID | None
    action: str
    workflow_code: str | None
    workflow_version: int | None
    actor_id: UUID | None
    created_at: datetime


class WorkflowDashboardResponse(BaseModel):
    metrics: list[WorkflowMetric]
    health_score: int
    recent_activity: list[WorkflowDashboardActivity]


class WorkflowDefinitionListItem(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    entity_type: str
    version: int
    is_published: bool
    is_active: bool
    states_count: int
    transitions_count: int
    instances_count: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class WorkflowDefinitionListResponse(BaseModel):
    items: list[WorkflowDefinitionListItem]
    total: int
    skip: int
    limit: int


class WorkflowStateDto(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    state_type: str
    sort_order: int
    is_initial: bool
    is_terminal: bool
    color_token: str | None
    icon: str | None
    is_active: bool
    incoming_count: int = 0
    outgoing_count: int = 0


class WorkflowTransitionDto(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    from_state_id: UUID
    to_state_id: UUID
    from_state_code: str | None
    to_state_code: str | None
    permission_code: str | None
    requires_comment: bool
    requires_reason: bool
    requires_attachment: bool
    confirmation_required: bool
    sort_order: int
    is_active: bool
    configuration_json: dict | None


class WorkflowSlaPolicyDto(BaseModel):
    id: UUID
    code: str
    name: str
    state_id: UUID | None
    state_code: str | None
    transition_id: UUID | None
    transition_code: str | None
    duration_minutes: int
    duration_label: str
    warning_before_minutes: int | None
    warning_label: str | None
    business_calendar_code: str | None
    severity: str
    is_active: bool


class WorkflowValidationIssue(BaseModel):
    code: str
    severity: str
    message: str
    target_type: str | None = None
    target_code: str | None = None


class WorkflowValidationResponse(BaseModel):
    status: str
    errors: list[WorkflowValidationIssue]
    warnings: list[WorkflowValidationIssue]
    info: list[WorkflowValidationIssue]


class WorkflowDefinitionDetailResponse(WorkflowDefinitionListItem):
    states: list[WorkflowStateDto]
    transitions: list[WorkflowTransitionDto]
    sla_policies: list[WorkflowSlaPolicyDto]
    validation: WorkflowValidationResponse
    created_by: UUID | None = None
    published_by: UUID | None = None


class WorkflowVersionItem(BaseModel):
    id: UUID
    code: str
    version: int
    status: str
    created_by: UUID | None
    created_at: datetime
    published_at: datetime | None
    comment: str | None
    instances_count: int
    is_active: bool
    is_published: bool


class WorkflowVersionListResponse(BaseModel):
    items: list[WorkflowVersionItem]
    total: int


class WorkflowVersionDiffResponse(BaseModel):
    source_version: int
    target_version: int
    added_states: list[str]
    removed_states: list[str]
    added_transitions: list[str]
    removed_transitions: list[str]
    permission_changes: list[str]
    sla_changes: list[str]
    metadata_changes: list[str]


class WorkflowInstanceListItem(BaseModel):
    id: UUID
    workflow_definition_id: UUID
    workflow_code: str
    workflow_name: str
    workflow_version: int
    entity_type: str
    entity_id: UUID
    business_identifier: str
    current_state: str
    current_state_code: str
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    lock_version: int


class WorkflowInstanceListResponse(BaseModel):
    items: list[WorkflowInstanceListItem]
    total: int
    skip: int
    limit: int


class WorkflowExecutionDto(BaseModel):
    id: UUID
    transition_code: str | None
    transition_name: str | None
    from_state: str | None
    to_state: str | None
    actor_type: str
    actor_id: UUID | None
    comment: str | None
    reason_code: str | None
    created_at: datetime
    correlation_id: str | None


class WorkflowSlaTimerDto(BaseModel):
    id: UUID
    policy_code: str | None
    policy_name: str | None
    started_at: datetime
    due_at: datetime
    warning_at: datetime | None
    completed_at: datetime | None
    breached_at: datetime | None
    status: str


class WorkflowOutboxDto(BaseModel):
    id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    business_identifier: str
    created_at: datetime
    processed_at: datetime | None
    status: str
    attempts: int
    correlation_id: str | None
    last_error: str | None


class WorkflowInstanceDetailResponse(WorkflowInstanceListItem):
    executions: list[WorkflowExecutionDto]
    sla_timers: list[WorkflowSlaTimerDto]
    outbox_events: list[WorkflowOutboxDto]
    metadata: dict
    technical_details: dict | None = None


class SlaCenterResponse(BaseModel):
    metrics: list[WorkflowMetric]
    policies: list[WorkflowSlaPolicyDto]
    timers: list[WorkflowSlaTimerDto]
    business_calendar_note: str


class OutboxMonitorResponse(BaseModel):
    metrics: list[WorkflowMetric]
    items: list[WorkflowOutboxDto]
    total: int
    skip: int
    limit: int


class ProcessAuditItem(BaseModel):
    id: UUID
    action: str
    workflow_code: str | None
    workflow_version: int | None
    actor_id: UUID | None
    actor_type: str
    created_at: datetime
    safe_details: dict | None


class ProcessAuditResponse(BaseModel):
    items: list[ProcessAuditItem]
    total: int
    skip: int
    limit: int


class WorkflowStatisticsResponse(BaseModel):
    average_workflow_duration: str
    median_duration: str
    fastest_transition: str
    slowest_transition: str
    average_completion_time: str
    completion_percent: float
    cancellation_percent: float
    sla_percent: float


class PlatformHealthItem(BaseModel):
    name: str
    status: str
    message: str


class PlatformHealthResponse(BaseModel):
    health_score: int
    backend_status: str
    database_status: str
    alembic_revision: str | None
    workflow_engine: str
    workflow_definitions: str
    workflow_instances: str
    rbac: str
    authentication: str
    storage: str
    smtp: str
    ldap: str
    adfs: str
    warnings: list[PlatformHealthItem]
    errors: list[PlatformHealthItem]


class WorkflowSearchResult(BaseModel):
    type: str
    label: str
    description: str | None
    target: str


class WorkflowSearchResponse(BaseModel):
    items: list[WorkflowSearchResult]
