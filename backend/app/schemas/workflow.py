from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.workflow import WorkflowActorType, WorkflowSlaStatus, WorkflowStateType


class WorkflowDefinitionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    entity_type: str = Field(min_length=2, max_length=128)


class WorkflowDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class WorkflowDefinitionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    entity_type: str
    version: int
    is_active: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}


class WorkflowStateCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    state_type: WorkflowStateType
    sort_order: int = 100
    is_initial: bool = False
    is_terminal: bool = False
    color_token: str | None = None
    icon: str | None = None
    is_active: bool = True


class WorkflowStateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    state_type: WorkflowStateType | None = None
    sort_order: int | None = None
    is_initial: bool | None = None
    is_terminal: bool | None = None
    color_token: str | None = None
    icon: str | None = None
    is_active: bool | None = None


class WorkflowStateResponse(BaseModel):
    id: UUID
    workflow_definition_id: UUID
    code: str
    name: str
    description: str | None
    state_type: WorkflowStateType
    sort_order: int
    is_initial: bool
    is_terminal: bool
    color_token: str | None
    icon: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class WorkflowTransitionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    from_state_id: UUID
    to_state_id: UUID
    permission_code: str | None = None
    requires_comment: bool = False
    requires_reason: bool = False
    requires_attachment: bool = False
    confirmation_required: bool = False
    sort_order: int = 100
    is_active: bool = True
    configuration_json: dict | None = None


class WorkflowTransitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    from_state_id: UUID | None = None
    to_state_id: UUID | None = None
    permission_code: str | None = None
    requires_comment: bool | None = None
    requires_reason: bool | None = None
    requires_attachment: bool | None = None
    confirmation_required: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    configuration_json: dict | None = None


class WorkflowTransitionResponse(BaseModel):
    id: UUID
    workflow_definition_id: UUID
    code: str
    name: str
    description: str | None
    from_state_id: UUID
    to_state_id: UUID
    permission_code: str | None
    requires_comment: bool
    requires_reason: bool
    requires_attachment: bool
    confirmation_required: bool
    sort_order: int
    is_active: bool
    configuration_json: dict | None

    model_config = {"from_attributes": True}


class WorkflowSlaPolicyCreate(BaseModel):
    state_id: UUID | None = None
    transition_id: UUID | None = None
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    duration_minutes: int = Field(gt=0)
    warning_before_minutes: int | None = Field(default=None, ge=0)
    business_calendar_code: str | None = None
    pause_in_state_codes: list[str] | None = None
    severity: str = "WARNING"
    is_active: bool = True


class WorkflowSlaPolicyUpdate(BaseModel):
    name: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    warning_before_minutes: int | None = Field(default=None, ge=0)
    business_calendar_code: str | None = None
    pause_in_state_codes: list[str] | None = None
    severity: str | None = None
    is_active: bool | None = None


class WorkflowSlaPolicyResponse(BaseModel):
    id: UUID
    workflow_definition_id: UUID
    state_id: UUID | None
    transition_id: UUID | None
    code: str
    name: str
    duration_minutes: int
    warning_before_minutes: int | None
    business_calendar_code: str | None
    pause_in_state_codes: list | None
    severity: str
    is_active: bool

    model_config = {"from_attributes": True}


class WorkflowInstanceResponse(BaseModel):
    id: UUID
    workflow_definition_id: UUID
    workflow_version: int
    entity_type: str
    entity_id: UUID
    instance_key: str
    parent_instance_id: UUID | None
    current_state: WorkflowStateResponse
    started_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    lock_version: int


class WorkflowTransitionExecuteRequest(BaseModel):
    comment: str | None = None
    reason_code: str | None = None
    input_data: dict | None = None
    lock_version: int | None = None


class WorkflowTransitionExecutionResponse(BaseModel):
    id: UUID
    workflow_instance_id: UUID
    transition_id: UUID
    from_state: WorkflowStateResponse
    to_state: WorkflowStateResponse
    actor_type: WorkflowActorType
    actor_id: UUID | None
    comment: str | None
    reason_code: str | None
    safe_result_data: dict | None
    created_at: datetime
    correlation_id: str | None


class WorkflowAvailableTransitionResponse(BaseModel):
    code: str
    name: str
    description: str | None
    requires_comment: bool
    requires_reason: bool
    requires_attachment: bool
    confirmation_required: bool
    sort_order: int


class WorkflowSlaTimerResponse(BaseModel):
    id: UUID
    workflow_instance_id: UUID
    sla_policy_id: UUID
    started_at: datetime
    due_at: datetime
    warning_at: datetime | None
    completed_at: datetime | None
    breached_at: datetime | None
    status: WorkflowSlaStatus

    model_config = {"from_attributes": True}
