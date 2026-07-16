from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.admin import User, UserType
from app.models.requests import (
    ContractorRequest,
    RequestAssignment,
    RequestAttachmentCategory,
    RequestHistoryActorType,
    RequestStatus,
)
from app.models.workflow import (
    DomainEventOutbox,
    DomainEventType,
    WorkflowActorType,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowState,
    WorkflowStateType,
    WorkflowTransition,
)
from app.schemas.workflow import WorkflowDefinitionCreate, WorkflowStateCreate, WorkflowTransitionCreate
from app.services.rbac_service import permission_codes_for_user
from app.services.workflow_adapters import WorkflowActor, WorkflowEntityAdapter, workflow_adapters
from app.services.workflow_definition_service import (
    add_workflow_state,
    add_workflow_transition,
    create_workflow_definition,
    publish_workflow_definition,
)
from app.services.workflow_engine import (
    add_outbox,
    execute_transition_with_callback,
    get_available_transitions,
    get_workflow_timeline,
    latest_definition,
    record_external_transition,
)


CONTRACTOR_REQUEST_ENTITY_TYPE = "CONTRACTOR_REQUEST"
CONTRACTOR_REQUEST_WORKFLOW_CODE = "CONTRACTOR_REQUEST"
DEFAULT_INSTANCE_KEY = "default"

APPROVED_REQUEST_STATE_CODES = [
    RequestStatus.DRAFT.value,
    RequestStatus.NEW.value,
    RequestStatus.PARTIALLY_ASSIGNED.value,
    RequestStatus.ASSIGNED.value,
    RequestStatus.IN_PROGRESS.value,
    RequestStatus.COMPLETED.value,
    RequestStatus.CLOSED.value,
    RequestStatus.CANCELLED.value,
]

REQUEST_STATE_TYPES = {
    RequestStatus.DRAFT: WorkflowStateType.INITIAL,
    RequestStatus.NEW: WorkflowStateType.ACTIVE,
    RequestStatus.PARTIALLY_ASSIGNED: WorkflowStateType.ACTIVE,
    RequestStatus.ASSIGNED: WorkflowStateType.ACTIVE,
    RequestStatus.IN_PROGRESS: WorkflowStateType.ACTIVE,
    RequestStatus.COMPLETED: WorkflowStateType.COMPLETED,
    RequestStatus.CLOSED: WorkflowStateType.CLOSED,
    RequestStatus.CANCELLED: WorkflowStateType.CANCELLED,
}

REQUEST_TERMINAL_STATES = {RequestStatus.CLOSED, RequestStatus.CANCELLED}

APPROVED_REQUEST_STATUS_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.DRAFT: {RequestStatus.NEW, RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED},
    RequestStatus.NEW: {RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED, RequestStatus.CANCELLED},
    RequestStatus.PARTIALLY_ASSIGNED: {RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.ASSIGNED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.IN_PROGRESS: {RequestStatus.COMPLETED, RequestStatus.CANCELLED},
    RequestStatus.COMPLETED: {RequestStatus.CLOSED, RequestStatus.IN_PROGRESS},
    RequestStatus.CLOSED: set(),
    RequestStatus.CANCELLED: set(),
}

REQUEST_TRANSITION_CODES: dict[tuple[RequestStatus, RequestStatus], str] = {
    (RequestStatus.DRAFT, RequestStatus.NEW): "PUBLISH_TO_NEW",
    (RequestStatus.DRAFT, RequestStatus.PARTIALLY_ASSIGNED): "PUBLISH_TO_PARTIALLY_ASSIGNED",
    (RequestStatus.DRAFT, RequestStatus.ASSIGNED): "PUBLISH_TO_ASSIGNED",
    (RequestStatus.NEW, RequestStatus.PARTIALLY_ASSIGNED): "ASSIGN_PARTIALLY",
    (RequestStatus.NEW, RequestStatus.ASSIGNED): "ASSIGN",
    (RequestStatus.NEW, RequestStatus.CANCELLED): "CANCEL_FROM_NEW",
    (RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED): "ASSIGN_REMAINING",
    (RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.IN_PROGRESS): "START_WORK_FROM_PARTIALLY_ASSIGNED",
    (RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.CANCELLED): "CANCEL_FROM_PARTIALLY_ASSIGNED",
    (RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS): "START_WORK",
    (RequestStatus.ASSIGNED, RequestStatus.CANCELLED): "CANCEL_FROM_ASSIGNED",
    (RequestStatus.IN_PROGRESS, RequestStatus.COMPLETED): "COMPLETE",
    (RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED): "CANCEL_FROM_IN_PROGRESS",
    (RequestStatus.COMPLETED, RequestStatus.CLOSED): "CLOSE",
    (RequestStatus.COMPLETED, RequestStatus.IN_PROGRESS): "REOPEN",
}

REQUEST_TRANSITION_NAMES = {
    "PUBLISH_TO_NEW": "Publish without assignment",
    "PUBLISH_TO_PARTIALLY_ASSIGNED": "Publish partially assigned",
    "PUBLISH_TO_ASSIGNED": "Publish assigned",
    "ASSIGN_PARTIALLY": "Assign partially",
    "ASSIGN": "Assign",
    "ASSIGN_REMAINING": "Assign remaining",
    "START_WORK_FROM_PARTIALLY_ASSIGNED": "Start work from partial assignment",
    "START_WORK": "Start work",
    "COMPLETE": "Complete",
    "CLOSE": "Close",
    "REOPEN": "Reopen",
    "CANCEL_FROM_NEW": "Cancel",
    "CANCEL_FROM_PARTIALLY_ASSIGNED": "Cancel",
    "CANCEL_FROM_ASSIGNED": "Cancel",
    "CANCEL_FROM_IN_PROGRESS": "Cancel",
}

REQUEST_TRANSITION_PERMISSIONS = {
    "PUBLISH_TO_NEW": "requests.publish",
    "PUBLISH_TO_PARTIALLY_ASSIGNED": "requests.publish",
    "PUBLISH_TO_ASSIGNED": "requests.publish",
    "ASSIGN_PARTIALLY": "requests.update",
    "ASSIGN": "requests.update",
    "ASSIGN_REMAINING": "requests.update",
    "START_WORK_FROM_PARTIALLY_ASSIGNED": None,
    "START_WORK": None,
    "COMPLETE": None,
    "CLOSE": "requests.close",
    "REOPEN": "requests.change_status",
    "CANCEL_FROM_NEW": None,
    "CANCEL_FROM_PARTIALLY_ASSIGNED": None,
    "CANCEL_FROM_ASSIGNED": None,
    "CANCEL_FROM_IN_PROGRESS": None,
}

REQUEST_TRANSITION_ALLOWED_PERMISSIONS = {
    "START_WORK_FROM_PARTIALLY_ASSIGNED": ["requests.change_status", "contractor.requests.update_status", "contractor.requests.accept"],
    "START_WORK": ["requests.change_status", "contractor.requests.update_status", "contractor.requests.accept"],
    "COMPLETE": ["requests.change_status", "contractor.requests.update_status"],
    "CANCEL_FROM_NEW": ["requests.change_status", "contractor.requests.update_status"],
    "CANCEL_FROM_PARTIALLY_ASSIGNED": ["requests.change_status", "contractor.requests.update_status"],
    "CANCEL_FROM_ASSIGNED": ["requests.change_status", "contractor.requests.update_status"],
    "CANCEL_FROM_IN_PROGRESS": ["requests.change_status", "contractor.requests.update_status"],
}


@dataclass(frozen=True)
class WorkflowConsistencyResult:
    ok: bool
    issues: list[str]
    instance_id: UUID | None = None


class ContractorRequestWorkflowAdapter(WorkflowEntityAdapter):
    entity_type = CONTRACTOR_REQUEST_ENTITY_TYPE

    def get_entity(self, db: Session, entity_id: UUID, actor: WorkflowActor) -> ContractorRequest:
        request = db.scalar(
            select(ContractorRequest)
            .where(ContractorRequest.id == entity_id)
            .options(
                selectinload(ContractorRequest.assignments),
                selectinload(ContractorRequest.work_types),
            )
        )
        if request is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        if actor.actor_type == WorkflowActorType.CONTRACTOR_USER.value:
            contractor_ids = set(actor.scope.get("contractor_ids") or [])
            if not contractor_ids or not any(assignment.contractor_id in contractor_ids for assignment in request.assignments):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
            if "contractor.requests.view" not in actor.permissions:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            return request
        if "requests.view" not in actor.permissions and "workflows.instances.view" not in actor.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return request

    def validate_start(self, db: Session, entity: ContractorRequest, actor: WorkflowActor) -> None:
        if entity.status.value not in APPROVED_REQUEST_STATE_CODES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unsupported request status")

    def validate_transition(self, db: Session, entity: ContractorRequest, transition: WorkflowTransition, actor: WorkflowActor, input_data: dict | None) -> None:
        expected_to_status = request_status_for_state(db, transition.to_state_id)
        if expected_to_status not in APPROVED_REQUEST_STATUS_TRANSITIONS[entity.status]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Invalid status transition: {entity.status} -> {expected_to_status}")

    def get_actor_scope(self, db: Session, entity: ContractorRequest, actor: WorkflowActor) -> dict:
        return {"request_id": str(entity.id), "status": entity.status.value}

    def apply_transition(self, db: Session, entity: ContractorRequest, transition: WorkflowTransition, actor: WorkflowActor, input_data: dict | None) -> dict:
        return {"request_id": str(entity.id), "status": entity.status.value, "compatibility_mode": True}

    def build_safe_context(self, entity: ContractorRequest) -> dict:
        return {
            "request_id": str(entity.id),
            "request_number": entity.request_number,
            "status": entity.status.value,
        }

    def build_notification_context(self, entity: ContractorRequest, transition: WorkflowTransition) -> dict:
        return {
            "request_id": str(entity.id),
            "request_number": entity.request_number,
            "transition": transition.code,
        }

    def get_required_attachments(self, transition: WorkflowTransition) -> list[str]:
        if transition.code == "COMPLETE":
            return [RequestAttachmentCategory.WORK_RESULT.value]
        return super().get_required_attachments(transition)


def register_contractor_request_workflow_adapter() -> None:
    workflow_adapters.register(ContractorRequestWorkflowAdapter())


def workflow_actor_from_user(user: User) -> WorkflowActor:
    return WorkflowActor(
        user=user,
        actor_id=user.id,
        actor_type=WorkflowActorType.CONTRACTOR_USER.value if user.user_type == UserType.CONTRACTOR else WorkflowActorType.INTERNAL_USER.value,
        permissions=permission_codes_for_user(user),
        scope={"contractor_ids": {membership.contractor_id for membership in user.contractor_memberships if membership.is_active}},
    )


def workflow_actor_from_request_history(actor_type: RequestHistoryActorType, actor_id: UUID | None = None) -> WorkflowActor:
    return WorkflowActor(
        user=None,
        actor_id=actor_id,
        actor_type=WorkflowActorType.CONTRACTOR_USER.value if actor_type == RequestHistoryActorType.CONTRACTOR_USER else WorkflowActorType.INTERNAL_USER.value,
        permissions=compatibility_permissions_for_actor(actor_type),
        scope={"contractor_ids": {actor_id} if actor_type == RequestHistoryActorType.CONTRACTOR_USER and actor_id is not None else set()},
    )


def system_workflow_actor() -> WorkflowActor:
    return WorkflowActor(
        user=None,
        actor_id=None,
        actor_type=WorkflowActorType.SYSTEM.value,
        permissions={"workflows.instances.view", "workflows.instances.transition"},
    )


def compatibility_permissions_for_actor(actor_type: RequestHistoryActorType) -> set[str]:
    if actor_type == RequestHistoryActorType.CONTRACTOR_USER:
        return {
            "contractor.requests.view",
            "contractor.requests.update_status",
            "contractor.requests.accept",
            "workflows.instances.view",
            "workflows.instances.transition",
        }
    return {
        "requests.view",
        "requests.publish",
        "requests.update",
        "requests.change_status",
        "requests.close",
        "workflows.instances.view",
        "workflows.instances.transition",
    }


def seed_contractor_request_workflow_definition(db: Session) -> WorkflowDefinition:
    definition = db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE,
            WorkflowDefinition.version == 1,
        )
    )
    if definition is not None and definition.is_published:
        return definition
    if definition is None:
        definition = create_workflow_definition(
            db,
            WorkflowDefinitionCreate(
                code=CONTRACTOR_REQUEST_WORKFLOW_CODE,
                name="Contractor Request",
                entity_type=CONTRACTOR_REQUEST_ENTITY_TYPE,
            ),
        )

    states_by_code = {
        state.code: state
        for state in db.scalars(select(WorkflowState).where(WorkflowState.workflow_definition_id == definition.id)).all()
    }
    for index, status_code in enumerate(APPROVED_REQUEST_STATE_CODES):
        request_status = RequestStatus(status_code)
        if status_code not in states_by_code:
            states_by_code[status_code] = add_workflow_state(
                db,
                definition.id,
                WorkflowStateCreate(
                    code=status_code,
                    name=status_code,
                    state_type=REQUEST_STATE_TYPES[request_status],
                    sort_order=(index + 1) * 10,
                    is_initial=request_status == RequestStatus.DRAFT,
                    is_terminal=request_status in REQUEST_TERMINAL_STATES,
                ),
            )

    transitions_by_code = {
        transition.code
        for transition in db.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_definition_id == definition.id)).all()
    }
    for index, ((from_status, to_status), transition_code) in enumerate(REQUEST_TRANSITION_CODES.items()):
        if transition_code in transitions_by_code:
            continue
        add_workflow_transition(
            db,
            definition.id,
            WorkflowTransitionCreate(
                code=transition_code,
                name=REQUEST_TRANSITION_NAMES[transition_code],
                from_state_id=states_by_code[from_status.value].id,
                to_state_id=states_by_code[to_status.value].id,
                permission_code=REQUEST_TRANSITION_PERMISSIONS[transition_code],
                sort_order=(index + 1) * 10,
                configuration_json={
                    "allowed_actor_types": [WorkflowActorType.INTERNAL_USER.value, WorkflowActorType.CONTRACTOR_USER.value],
                    "allowed_permissions": REQUEST_TRANSITION_ALLOWED_PERMISSIONS.get(transition_code, []),
                },
            ),
        )

    if not definition.is_published:
        publish_workflow_definition(db, definition.id)
    db.flush()
    return definition


def contractor_request_definition_v1(db: Session) -> WorkflowDefinition:
    definition = db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE,
            WorkflowDefinition.version == 1,
            WorkflowDefinition.is_published.is_(True),
            WorkflowDefinition.is_active.is_(True),
        )
    )
    if definition is None:
        definition = seed_contractor_request_workflow_definition(db)
    return definition


def state_for_request_status(db: Session, definition_id: UUID, request_status: RequestStatus) -> WorkflowState:
    state = db.scalar(
        select(WorkflowState).where(
            WorkflowState.workflow_definition_id == definition_id,
            WorkflowState.code == request_status.value,
            WorkflowState.is_active.is_(True),
        )
    )
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow state for request status not found")
    return state


def request_status_for_state(db: Session, state_id: UUID) -> RequestStatus:
    state = db.get(WorkflowState, state_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow state not found")
    return RequestStatus(state.code)


def transition_code_for_status_change(old_status: RequestStatus, new_status: RequestStatus) -> str | None:
    return REQUEST_TRANSITION_CODES.get((old_status, new_status))


def execute_request_status_transition(
    db: Session,
    request: ContractorRequest,
    old_status: RequestStatus,
    new_status: RequestStatus,
    actor: WorkflowActor,
    apply_change,
    comment: str | None = None,
    input_data: dict | None = None,
    idempotency_key: str | None = None,
):
    register_contractor_request_workflow_adapter()
    ensure_instance_for_request(db, request)
    transition_code = transition_code_for_status_change(old_status, new_status)
    if old_status == new_status or transition_code is None:
        result = apply_change()
        synchronize_instance_from_request(db, request)
        return result

    def callback(entity: ContractorRequest, transition: WorkflowTransition) -> dict:
        result = apply_change()
        if request.status != new_status:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request status did not match workflow transition result")
        return {
            "request_id": str(request.id),
            "old_status": old_status.value,
            "new_status": new_status.value,
            "compatibility_mode": True,
        }

    return execute_transition_with_callback(
        db,
        CONTRACTOR_REQUEST_ENTITY_TYPE,
        request.id,
        transition_code,
        actor,
        apply_callback=callback,
        comment=comment,
        input_data=input_data or {"old_status": old_status.value, "new_status": new_status.value},
        idempotency_key=idempotency_key,
        workflow_code=CONTRACTOR_REQUEST_WORKFLOW_CODE,
    )


def record_request_status_transition_after_change(
    db: Session,
    request: ContractorRequest,
    old_status: RequestStatus,
    actor: WorkflowActor,
    comment: str | None = None,
    input_data: dict | None = None,
    idempotency_key: str | None = None,
) -> None:
    register_contractor_request_workflow_adapter()
    if old_status == request.status:
        synchronize_instance_from_request(db, request)
        return
    transition_code = transition_code_for_status_change(old_status, request.status)
    if transition_code is None:
        synchronize_instance_from_request(db, request)
        return
    ensure_instance_for_request(db, request)
    record_external_transition(
        db,
        CONTRACTOR_REQUEST_ENTITY_TYPE,
        request.id,
        transition_code,
        actor,
        comment=comment,
        input_data=input_data or {"old_status": old_status.value, "new_status": request.status.value},
        safe_result_data={"request_id": str(request.id), "new_status": request.status.value, "compatibility_mode": True},
        idempotency_key=idempotency_key,
        workflow_code=CONTRACTOR_REQUEST_WORKFLOW_CODE,
    )


def ensure_instance_for_request(db: Session, request: ContractorRequest) -> WorkflowInstance:
    definition = contractor_request_definition_v1(db)
    existing = db.scalar(
        select(WorkflowInstance).where(
            WorkflowInstance.workflow_definition_id == definition.id,
            WorkflowInstance.entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE,
            WorkflowInstance.entity_id == request.id,
            WorkflowInstance.instance_key == DEFAULT_INSTANCE_KEY,
        )
    )
    if existing is not None:
        return existing
    state = state_for_request_status(db, definition.id, request.status)
    instance = WorkflowInstance(
        workflow_definition_id=definition.id,
        workflow_version=definition.version,
        entity_type=CONTRACTOR_REQUEST_ENTITY_TYPE,
        entity_id=request.id,
        instance_key=DEFAULT_INSTANCE_KEY,
        current_state_id=state.id,
        started_at=request.created_at,
        completed_at=request.completed_at if request.status in {RequestStatus.COMPLETED, RequestStatus.CLOSED} else None,
        cancelled_at=None,
        lock_version=1,
    )
    db.add(instance)
    db.flush()
    return instance


def synchronize_instance_from_request(db: Session, request: ContractorRequest) -> WorkflowInstance:
    instance = ensure_instance_for_request(db, request)
    state = state_for_request_status(db, instance.workflow_definition_id, request.status)
    changed = instance.current_state_id != state.id
    instance.current_state_id = state.id
    instance.completed_at = request.completed_at if request.status in {RequestStatus.COMPLETED, RequestStatus.CLOSED} else None
    instance.cancelled_at = request.updated_at if request.status == RequestStatus.CANCELLED else None
    if changed:
        instance.lock_version += 1
    db.flush()
    return instance


def verify_request_workflow_consistency(db: Session, request: ContractorRequest) -> WorkflowConsistencyResult:
    definition = contractor_request_definition_v1(db)
    instances = list(
        db.scalars(
            select(WorkflowInstance).where(
                WorkflowInstance.workflow_definition_id == definition.id,
                WorkflowInstance.entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE,
                WorkflowInstance.entity_id == request.id,
                WorkflowInstance.instance_key == DEFAULT_INSTANCE_KEY,
            )
        ).all()
    )
    issues: list[str] = []
    if not instances:
        issues.append("missing_instance")
        return WorkflowConsistencyResult(ok=False, issues=issues)
    if len(instances) > 1:
        issues.append("duplicate_default_instances")
    instance = instances[0]
    expected = state_for_request_status(db, definition.id, request.status)
    current = db.get(WorkflowState, instance.current_state_id)
    if current is None or current.id != expected.id:
        issues.append("state_mismatch")
    if instance.workflow_version != definition.version:
        issues.append("wrong_workflow_version")
    return WorkflowConsistencyResult(ok=not issues, issues=issues, instance_id=instance.id)


def backfill_contractor_request_workflow_instances(db: Session, dry_run: bool = False) -> dict[str, int]:
    seed_contractor_request_workflow_definition(db)
    created = 0
    existing = 0
    requests = db.scalars(select(ContractorRequest).order_by(ContractorRequest.created_at.asc())).all()
    for request in requests:
        before = db.scalar(
            select(WorkflowInstance.id)
            .join(WorkflowDefinition)
            .where(
                WorkflowDefinition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE,
                WorkflowDefinition.version == 1,
                WorkflowInstance.entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE,
                WorkflowInstance.entity_id == request.id,
                WorkflowInstance.instance_key == DEFAULT_INSTANCE_KEY,
            )
        )
        if before is not None:
            existing += 1
            continue
        if not dry_run:
            ensure_instance_for_request(db, request)
        created += 1
    if not dry_run:
        db.flush()
    return {"created": created, "existing": existing, "checked": len(requests)}


def workflow_instances_for_request(db: Session, request_id: UUID) -> list[WorkflowInstance]:
    definition = contractor_request_definition_v1(db)
    return list(
        db.scalars(
            select(WorkflowInstance).where(
                WorkflowInstance.workflow_definition_id == definition.id,
                WorkflowInstance.entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE,
                WorkflowInstance.entity_id == request_id,
                WorkflowInstance.instance_key == DEFAULT_INSTANCE_KEY,
            )
        ).all()
    )


def add_request_workflow_outbox_once(db: Session, instance: WorkflowInstance, transition_code: str | None) -> None:
    if transition_code is None:
        return
    existing = db.scalar(
        select(DomainEventOutbox.id).where(
            DomainEventOutbox.event_type == DomainEventType.WORKFLOW_TRANSITION_EXECUTED.value,
            DomainEventOutbox.aggregate_type == CONTRACTOR_REQUEST_ENTITY_TYPE,
            DomainEventOutbox.aggregate_id == instance.entity_id,
            DomainEventOutbox.payload["transition"].as_string() == transition_code,
        )
    )
    if existing is None:
        add_outbox(db, DomainEventType.WORKFLOW_TRANSITION_EXECUTED, instance, {"transition": transition_code, "compatibility": True})


def available_contractor_request_transitions(db: Session, request_id: UUID, actor: WorkflowActor) -> list[WorkflowTransition]:
    instance = workflow_instances_for_request(db, request_id)[0]
    return get_available_transitions(db, instance, actor)


def contractor_request_timeline(db: Session, request_id: UUID, actor: WorkflowActor):
    instance = workflow_instances_for_request(db, request_id)[0]
    return get_workflow_timeline(db, instance)
