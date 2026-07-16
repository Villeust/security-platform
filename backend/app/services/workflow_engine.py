from datetime import timedelta
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.correlation import get_correlation_id
from app.models.reference_data import utc_now
from app.models.workflow import (
    DomainEventOutbox,
    DomainEventType,
    WorkflowActorType,
    WorkflowDefinition,
    WorkflowIdempotencyRecord,
    WorkflowInstance,
    WorkflowSlaPolicy,
    WorkflowSlaStatus,
    WorkflowSlaTimer,
    WorkflowState,
    WorkflowStateType,
    WorkflowTransition,
    WorkflowTransitionExecution,
)
from app.services.audit_service import write_audit
from app.services.workflow_adapters import WorkflowActor, workflow_adapters


SAFE_CONFIG_KEYS = {"required_fields", "required_attachment_categories", "minimum_attachment_count", "allowed_actor_types", "allowed_permissions"}


def workflow_actor_id(actor: WorkflowActor) -> UUID | None:
    return actor.actor_id or (actor.user.id if actor.user is not None else None)


def workflow_audit_actor_id(actor: WorkflowActor) -> UUID | None:
    return actor.user.id if actor.user is not None else None


def latest_definition(db: Session, entity_type: str, workflow_code: str | None = None) -> WorkflowDefinition:
    query = select(WorkflowDefinition).where(
        WorkflowDefinition.entity_type == entity_type,
        WorkflowDefinition.is_active.is_(True),
        WorkflowDefinition.is_published.is_(True),
    )
    if workflow_code is not None:
        query = query.where(WorkflowDefinition.code == workflow_code)
    definition = db.scalar(query.order_by(WorkflowDefinition.version.desc()))
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow definition not found")
    return definition


def initial_state(db: Session, definition_id: UUID) -> WorkflowState:
    state = db.scalar(select(WorkflowState).where(WorkflowState.workflow_definition_id == definition_id, WorkflowState.is_initial.is_(True), WorkflowState.is_active.is_(True)))
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow has no initial state")
    return state


def get_instance_or_404(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    actor: WorkflowActor,
    workflow_code: str | None = None,
    instance_key: str = "default",
) -> WorkflowInstance:
    adapter = workflow_adapters.get(entity_type)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow adapter not found")
    adapter.get_entity(db, entity_id, actor)
    query = (
        select(WorkflowInstance)
        .join(WorkflowDefinition)
        .where(
            WorkflowInstance.entity_type == entity_type,
            WorkflowInstance.entity_id == entity_id,
            WorkflowInstance.instance_key == instance_key,
        )
        .order_by(WorkflowInstance.created_at.desc())
    )
    if workflow_code is not None:
        query = query.where(WorkflowDefinition.code == workflow_code)
    instance = db.scalar(query)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow instance not found")
    return instance


def start_workflow(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    actor: WorkflowActor,
    workflow_code: str | None = None,
    instance_key: str = "default",
    parent_instance_id: UUID | None = None,
) -> WorkflowInstance:
    adapter = workflow_adapters.get(entity_type)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow adapter not found")
    definition = latest_definition(db, entity_type, workflow_code)
    existing = db.scalar(
        select(WorkflowInstance).where(
            WorkflowInstance.workflow_definition_id == definition.id,
            WorkflowInstance.entity_type == entity_type,
            WorkflowInstance.entity_id == entity_id,
            WorkflowInstance.instance_key == instance_key,
        )
    )
    if existing is not None:
        return existing
    entity = adapter.get_entity(db, entity_id, actor)
    adapter.validate_start(db, entity, actor)
    state = initial_state(db, definition.id)
    now = utc_now()
    instance = WorkflowInstance(
        workflow_definition_id=definition.id,
        workflow_version=definition.version,
        entity_type=entity_type,
        entity_id=entity_id,
        instance_key=instance_key,
        parent_instance_id=parent_instance_id,
        current_state_id=state.id,
        started_at=now,
    )
    db.add(instance)
    db.flush()
    create_sla_timers(db, instance, state_id=state.id, transition_id=None, now=now)
    add_outbox(db, DomainEventType.WORKFLOW_STARTED, instance, {"state": state.code, "context": adapter.build_safe_context(entity)})
    write_audit(db, "WORKFLOW_STARTED", "WorkflowInstance", instance.id, actor_id=workflow_audit_actor_id(actor), actor_type=actor.actor_type, new_data={"entity_type": entity_type, "entity_id": str(entity_id)})
    db.flush()
    return instance


def get_available_transitions(db: Session, instance: WorkflowInstance, actor: WorkflowActor) -> list[WorkflowTransition]:
    current_state = db.get(WorkflowState, instance.current_state_id)
    if current_state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow current state is missing")
    if current_state.is_terminal:
        return []
    transitions = db.scalars(
        select(WorkflowTransition)
        .where(
            WorkflowTransition.workflow_definition_id == instance.workflow_definition_id,
            WorkflowTransition.from_state_id == instance.current_state_id,
            WorkflowTransition.is_active.is_(True),
        )
        .order_by(WorkflowTransition.sort_order)
    ).all()
    return [transition for transition in transitions if can_execute_transition(db, instance, transition, actor, raise_on_error=False)]


def can_execute_transition(db: Session, instance: WorkflowInstance, transition: WorkflowTransition, actor: WorkflowActor, raise_on_error: bool = True) -> bool:
    try:
        if transition.workflow_definition_id != instance.workflow_definition_id or transition.from_state_id != instance.current_state_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transition is not valid for current workflow state")
        if transition.permission_code and transition.permission_code not in actor.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transition permission denied")
        configuration = transition.configuration_json or {}
        unsafe = set(configuration) - SAFE_CONFIG_KEYS
        if unsafe:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow transition configuration contains unsupported keys")
        allowed_permissions = set(configuration.get("allowed_permissions") or [])
        if allowed_permissions and actor.permissions.isdisjoint(allowed_permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transition permission denied")
        allowed_actor_types = set(configuration.get("allowed_actor_types") or [])
        if allowed_actor_types and actor.actor_type not in allowed_actor_types:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor type is not allowed for transition")
        return True
    except HTTPException:
        if raise_on_error:
            raise
        return False


def execute_transition(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    transition_code: str,
    actor: WorkflowActor,
    comment: str | None = None,
    reason_code: str | None = None,
    input_data: dict | None = None,
    lock_version: int | None = None,
    idempotency_key: str | None = None,
    workflow_code: str | None = None,
    instance_key: str = "default",
) -> WorkflowTransitionExecution:
    return execute_transition_with_callback(
        db,
        entity_type,
        entity_id,
        transition_code,
        actor,
        apply_callback=None,
        comment=comment,
        reason_code=reason_code,
        input_data=input_data,
        lock_version=lock_version,
        idempotency_key=idempotency_key,
        workflow_code=workflow_code,
        instance_key=instance_key,
    )


def execute_transition_with_callback(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    transition_code: str,
    actor: WorkflowActor,
    apply_callback=None,
    comment: str | None = None,
    reason_code: str | None = None,
    input_data: dict | None = None,
    lock_version: int | None = None,
    idempotency_key: str | None = None,
    workflow_code: str | None = None,
    instance_key: str = "default",
) -> WorkflowTransitionExecution:
    adapter = workflow_adapters.get(entity_type)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow adapter not found")
    entity = adapter.get_entity(db, entity_id, actor)
    instance = get_instance_or_404(db, entity_type, entity_id, actor, workflow_code=workflow_code, instance_key=instance_key)
    if lock_version is not None and lock_version != instance.lock_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow state is stale")
    transition = db.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.workflow_definition_id == instance.workflow_definition_id,
            WorkflowTransition.code == transition_code,
            WorkflowTransition.is_active.is_(True),
        )
    )
    if transition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transition not found")
    current_request_hash = transition_request_hash(comment, reason_code, input_data, lock_version)
    if idempotency_key:
        existing = db.scalar(
            select(WorkflowIdempotencyRecord).where(
                WorkflowIdempotencyRecord.key == idempotency_key,
                WorkflowIdempotencyRecord.workflow_instance_id == instance.id,
                WorkflowIdempotencyRecord.transition_id == transition.id,
            )
        )
        if existing is not None:
            if existing.request_hash != current_request_hash:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key was already used for a different transition request")
            execution_id = existing.safe_response_data.get("execution_id")
            execution = db.get(WorkflowTransitionExecution, UUID(execution_id)) if execution_id else None
            if execution is not None:
                return execution
    can_execute_transition(db, instance, transition, actor)
    if transition.requires_comment and not comment:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment is required")
    if transition.requires_reason and not reason_code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reason is required")
    validate_required_fields(transition, input_data)
    adapter.validate_transition(db, entity, transition, actor, input_data)
    result = apply_callback(entity, transition) if apply_callback is not None else adapter.apply_transition(db, entity, transition, actor, input_data)
    now = utc_now()
    execution = WorkflowTransitionExecution(
        workflow_instance_id=instance.id,
        transition_id=transition.id,
        from_state_id=instance.current_state_id,
        to_state_id=transition.to_state_id,
        actor_type=WorkflowActorType(actor.actor_type),
        actor_id=workflow_actor_id(actor),
        comment=comment,
        reason_code=reason_code,
        input_data=safe_json(input_data),
        safe_result_data=safe_json(result),
        correlation_id=get_correlation_id() or idempotency_key,
    )
    instance.current_state_id = transition.to_state_id
    instance.lock_version += 1
    to_state = db.get(WorkflowState, transition.to_state_id)
    if to_state and to_state.state_type in {WorkflowStateType.COMPLETED, WorkflowStateType.CLOSED}:
        instance.completed_at = now
    if to_state and to_state.state_type == WorkflowStateType.CANCELLED:
        instance.cancelled_at = now
    complete_active_sla_timers(db, instance, now)
    create_sla_timers(db, instance, state_id=transition.to_state_id, transition_id=transition.id, now=now)
    db.add(execution)
    db.flush()
    add_outbox(db, DomainEventType.WORKFLOW_TRANSITION_EXECUTED, instance, {"transition": transition.code, "from_state_id": str(execution.from_state_id), "to_state_id": str(execution.to_state_id), "result": safe_json(result)})
    add_outbox(db, DomainEventType.WORKFLOW_STATE_CHANGED, instance, {"transition": transition.code, "state_id": str(transition.to_state_id)})
    write_audit(db, "WORKFLOW_TRANSITION_EXECUTED", "WorkflowInstance", instance.id, actor_id=workflow_audit_actor_id(actor), actor_type=actor.actor_type, new_data={"transition": transition.code})
    if idempotency_key:
        db.add(
            WorkflowIdempotencyRecord(
                key=idempotency_key,
                workflow_instance_id=instance.id,
                transition_id=transition.id,
                request_hash=current_request_hash,
                safe_response_data={"execution_id": str(execution.id)},
                expires_at=now + timedelta(hours=24),
            )
        )
    adapter.after_transition(db, entity, transition, actor)
    db.flush()
    return execution


def record_external_transition(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    transition_code: str,
    actor: WorkflowActor,
    comment: str | None = None,
    reason_code: str | None = None,
    input_data: dict | None = None,
    safe_result_data: dict | None = None,
    idempotency_key: str | None = None,
    workflow_code: str | None = None,
    instance_key: str = "default",
) -> WorkflowTransitionExecution:
    adapter = workflow_adapters.get(entity_type)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow adapter not found")
    adapter.get_entity(db, entity_id, actor)
    instance = get_instance_or_404(db, entity_type, entity_id, actor, workflow_code=workflow_code, instance_key=instance_key)
    transition = db.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.workflow_definition_id == instance.workflow_definition_id,
            WorkflowTransition.code == transition_code,
            WorkflowTransition.is_active.is_(True),
        )
    )
    if transition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transition not found")
    can_execute_transition(db, instance, transition, actor)
    now = utc_now()
    execution = WorkflowTransitionExecution(
        workflow_instance_id=instance.id,
        transition_id=transition.id,
        from_state_id=instance.current_state_id,
        to_state_id=transition.to_state_id,
        actor_type=WorkflowActorType(actor.actor_type),
        actor_id=workflow_actor_id(actor),
        comment=comment,
        reason_code=reason_code,
        input_data=safe_json(input_data),
        safe_result_data=safe_json(safe_result_data),
        correlation_id=get_correlation_id() or idempotency_key,
    )
    instance.current_state_id = transition.to_state_id
    instance.lock_version += 1
    to_state = db.get(WorkflowState, transition.to_state_id)
    if to_state and to_state.state_type in {WorkflowStateType.COMPLETED, WorkflowStateType.CLOSED}:
        instance.completed_at = now
    if to_state and to_state.state_type == WorkflowStateType.CANCELLED:
        instance.cancelled_at = now
    complete_active_sla_timers(db, instance, now)
    create_sla_timers(db, instance, state_id=transition.to_state_id, transition_id=transition.id, now=now)
    db.add(execution)
    db.flush()
    add_outbox(db, DomainEventType.WORKFLOW_TRANSITION_EXECUTED, instance, {"transition": transition.code, "from_state_id": str(execution.from_state_id), "to_state_id": str(execution.to_state_id), "result": safe_json(safe_result_data)})
    add_outbox(db, DomainEventType.WORKFLOW_STATE_CHANGED, instance, {"transition": transition.code, "state_id": str(transition.to_state_id)})
    write_audit(db, "WORKFLOW_TRANSITION_EXECUTED", "WorkflowInstance", instance.id, actor_id=workflow_audit_actor_id(actor), actor_type=actor.actor_type, new_data={"transition": transition.code, "external_apply": True})
    db.flush()
    return execution


def get_workflow_timeline(db: Session, instance: WorkflowInstance) -> list[WorkflowTransitionExecution]:
    return list(db.scalars(select(WorkflowTransitionExecution).where(WorkflowTransitionExecution.workflow_instance_id == instance.id).order_by(WorkflowTransitionExecution.created_at.asc())).all())


def cancel_workflow(db: Session, instance: WorkflowInstance, actor: WorkflowActor, reason_code: str | None = None) -> WorkflowInstance:
    current_state = db.get(WorkflowState, instance.current_state_id)
    if current_state is not None and current_state.is_terminal:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow is already terminal")
    cancelled = db.scalar(select(WorkflowState).where(WorkflowState.workflow_definition_id == instance.workflow_definition_id, WorkflowState.state_type == WorkflowStateType.CANCELLED))
    if cancelled is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow has no cancelled state")
    instance.current_state_id = cancelled.id
    instance.cancelled_at = utc_now()
    instance.lock_version += 1
    add_outbox(db, DomainEventType.WORKFLOW_CANCELLED, instance, {"reason_code": reason_code})
    write_audit(db, "WORKFLOW_CANCELLED", "WorkflowInstance", instance.id, actor_id=workflow_audit_actor_id(actor), actor_type=actor.actor_type, new_data={"reason_code": reason_code})
    db.flush()
    return instance


def migrate_instance_version(*args, **kwargs) -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Automatic workflow version migration is disabled")


def validate_required_fields(transition: WorkflowTransition, input_data: dict | None) -> None:
    configuration = transition.configuration_json or {}
    fields = configuration.get("required_fields") or []
    data = input_data or {}
    missing = [field for field in fields if data.get(field) in (None, "")]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Missing required fields: {', '.join(missing)}")


def transition_request_hash(comment: str | None, reason_code: str | None, input_data: dict | None, lock_version: int | None) -> str:
    payload = {
        "comment": comment,
        "reason_code": reason_code,
        "input_data": safe_json(input_data),
        "lock_version": lock_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def safe_json(value: dict | None) -> dict | None:
    if value is None:
        return None
    forbidden = {"password", "token", "secret", "authorization", "cookie", "headers"}
    return {key: scrub_safe_value(key, item, forbidden) for key, item in value.items()}


def scrub_safe_value(key: str, value, forbidden: set[str]):
    lowered = key.lower()
    if lowered in forbidden or any(part in lowered for part in ("password", "token", "secret")):
        return "***"
    if isinstance(value, dict):
        return {child_key: scrub_safe_value(child_key, child_value, forbidden) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [scrub_safe_value(key, item, forbidden) for item in value]
    return value


def add_outbox(db: Session, event_type: DomainEventType, instance: WorkflowInstance, payload: dict) -> None:
    db.add(
        DomainEventOutbox(
            event_type=event_type.value,
            aggregate_type=instance.entity_type,
            aggregate_id=instance.entity_id,
            payload=safe_json(payload) or {},
            correlation_id=get_correlation_id(),
        )
    )


def create_sla_timers(db: Session, instance: WorkflowInstance, state_id: UUID | None, transition_id: UUID | None, now) -> None:
    policies = db.scalars(
        select(WorkflowSlaPolicy).where(
            WorkflowSlaPolicy.workflow_definition_id == instance.workflow_definition_id,
            WorkflowSlaPolicy.is_active.is_(True),
        )
    ).all()
    for policy in policies:
        if policy.state_id not in (None, state_id):
            continue
        if policy.transition_id not in (None, transition_id):
            continue
        warning_at = now + timedelta(minutes=max(0, policy.duration_minutes - policy.warning_before_minutes)) if policy.warning_before_minutes is not None else None
        db.add(
            WorkflowSlaTimer(
                workflow_instance_id=instance.id,
                sla_policy_id=policy.id,
                started_at=now,
                due_at=now + timedelta(minutes=policy.duration_minutes),
                warning_at=warning_at,
                status=WorkflowSlaStatus.ACTIVE,
            )
        )


def complete_active_sla_timers(db: Session, instance: WorkflowInstance, now) -> None:
    timers = db.scalars(select(WorkflowSlaTimer).where(WorkflowSlaTimer.workflow_instance_id == instance.id, WorkflowSlaTimer.status == WorkflowSlaStatus.ACTIVE)).all()
    for timer in timers:
        timer.status = WorkflowSlaStatus.COMPLETED
        timer.completed_at = now


def mark_breached_sla_timers(db: Session, now) -> int:
    db.flush()
    timers = db.scalars(select(WorkflowSlaTimer).where(WorkflowSlaTimer.status == WorkflowSlaStatus.ACTIVE, WorkflowSlaTimer.due_at < now)).all()
    for timer in timers:
        timer.status = WorkflowSlaStatus.BREACHED
        timer.breached_at = now
        db.add(
            DomainEventOutbox(
                event_type=DomainEventType.SLA_BREACHED.value,
                aggregate_type="WorkflowSlaTimer",
                aggregate_id=timer.id,
                payload={"workflow_instance_id": str(timer.workflow_instance_id)},
                correlation_id=get_correlation_id(),
            )
        )
    db.flush()
    return len(timers)
