from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_stub, require_csrf
from app.db.session import get_db
from app.models.admin import User
from app.models.workflow import WorkflowInstance, WorkflowTransition, WorkflowTransitionExecution
from app.schemas.workflow import (
    WorkflowAvailableTransitionResponse,
    WorkflowInstanceResponse,
    WorkflowTransitionExecutionResponse,
)
from app.services.contractor_request_workflow import (
    CONTRACTOR_REQUEST_ENTITY_TYPE,
    CONTRACTOR_REQUEST_WORKFLOW_CODE,
    register_contractor_request_workflow_adapter,
    workflow_actor_from_user,
)
from app.services.workflow_adapters import workflow_adapters
from app.services.workflow_engine import get_available_transitions, get_instance_or_404, get_workflow_timeline

router = APIRouter(prefix="/workflows", tags=["workflows"])

SUPPORTED_ENTITY_TYPES = {CONTRACTOR_REQUEST_ENTITY_TYPE}


def ensure_supported_entity_type(entity_type: str) -> None:
    if entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE:
        register_contractor_request_workflow_adapter()
    if entity_type not in SUPPORTED_ENTITY_TYPES or workflow_adapters.get(entity_type) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow adapter not found")


def workflow_code_for_entity_type(entity_type: str) -> str:
    if entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE:
        return CONTRACTOR_REQUEST_WORKFLOW_CODE
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow adapter not found")


def serialize_instance(instance: WorkflowInstance) -> WorkflowInstanceResponse:
    return WorkflowInstanceResponse(
        id=instance.id,
        workflow_definition_id=instance.workflow_definition_id,
        workflow_version=instance.workflow_version,
        entity_type=instance.entity_type,
        entity_id=instance.entity_id,
        instance_key=instance.instance_key,
        parent_instance_id=instance.parent_instance_id,
        current_state=instance.current_state,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
        cancelled_at=instance.cancelled_at,
        lock_version=instance.lock_version,
    )


def serialize_transition(transition: WorkflowTransition) -> WorkflowAvailableTransitionResponse:
    return WorkflowAvailableTransitionResponse(
        code=transition.code,
        name=transition.name,
        description=transition.description,
        requires_comment=transition.requires_comment,
        requires_reason=transition.requires_reason,
        requires_attachment=transition.requires_attachment,
        confirmation_required=transition.confirmation_required,
        sort_order=transition.sort_order,
    )


def serialize_execution(execution: WorkflowTransitionExecution) -> WorkflowTransitionExecutionResponse:
    return WorkflowTransitionExecutionResponse(
        id=execution.id,
        workflow_instance_id=execution.workflow_instance_id,
        transition_id=execution.transition_id,
        from_state=execution.from_state,
        to_state=execution.to_state,
        actor_type=execution.actor_type,
        actor_id=execution.actor_id,
        comment=execution.comment,
        reason_code=execution.reason_code,
        safe_result_data=execution.safe_result_data,
        created_at=execution.created_at,
        correlation_id=execution.correlation_id,
    )


@router.get("/instances/{entity_type}/{entity_id}", response_model=WorkflowInstanceResponse)
def get_workflow_instance(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_stub),
) -> WorkflowInstanceResponse:
    ensure_supported_entity_type(entity_type)
    actor = workflow_actor_from_user(user)
    instance = get_instance_or_404(db, entity_type, entity_id, actor, workflow_code=workflow_code_for_entity_type(entity_type))
    return serialize_instance(instance)


@router.get("/instances/{entity_type}/{entity_id}/transitions", response_model=list[WorkflowAvailableTransitionResponse])
def list_workflow_transitions(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_stub),
) -> list[WorkflowAvailableTransitionResponse]:
    ensure_supported_entity_type(entity_type)
    actor = workflow_actor_from_user(user)
    instance = get_instance_or_404(db, entity_type, entity_id, actor, workflow_code=workflow_code_for_entity_type(entity_type))
    return [serialize_transition(item) for item in get_available_transitions(db, instance, actor)]


@router.get("/instances/{entity_type}/{entity_id}/timeline", response_model=list[WorkflowTransitionExecutionResponse])
def get_workflow_instance_timeline(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_stub),
) -> list[WorkflowTransitionExecutionResponse]:
    ensure_supported_entity_type(entity_type)
    actor = workflow_actor_from_user(user)
    instance = get_instance_or_404(db, entity_type, entity_id, actor, workflow_code=workflow_code_for_entity_type(entity_type))
    return [serialize_execution(item) for item in get_workflow_timeline(db, instance)]


@router.post("/instances/{entity_type}/{entity_id}/transitions/{transition_code}")
def execute_workflow_transition_disabled(
    entity_type: str,
    entity_id: UUID,
    transition_code: str,
    _: None = Depends(require_csrf),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    ensure_supported_entity_type(entity_type)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generic workflow mutation is disabled for Contractor Requests in Phase 2")
