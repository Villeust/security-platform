from collections.abc import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.admin import Permission
from app.models.reference_data import utc_now
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowSlaPolicy,
    WorkflowState,
    WorkflowTransition,
)
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowSlaPolicyCreate,
    WorkflowSlaPolicyUpdate,
    WorkflowStateCreate,
    WorkflowStateUpdate,
    WorkflowTransitionCreate,
    WorkflowTransitionUpdate,
)
from app.services.audit_service import write_audit
from app.services.workflow_engine import SAFE_CONFIG_KEYS


def get_definition_or_404(db: Session, definition_id: UUID) -> WorkflowDefinition:
    definition = db.scalar(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == definition_id)
        .options(
            selectinload(WorkflowDefinition.states),
            selectinload(WorkflowDefinition.transitions),
            selectinload(WorkflowDefinition.sla_policies),
        )
    )
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow definition not found")
    return definition


def ensure_draft(definition: WorkflowDefinition) -> None:
    if definition.is_published:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Published workflow definition is immutable")


def validate_configuration(configuration: dict | None) -> None:
    if configuration is None:
        return
    unsafe = set(configuration) - SAFE_CONFIG_KEYS
    if unsafe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow transition configuration contains unsupported keys")
    for key in ("required_fields", "required_attachment_categories", "allowed_actor_types", "allowed_permissions"):
        if key in configuration and not isinstance(configuration[key], list):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{key} must be a list")
    if "minimum_attachment_count" in configuration:
        value = configuration["minimum_attachment_count"]
        if not isinstance(value, int) or value < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="minimum_attachment_count must be a non-negative integer")


def create_workflow_definition(db: Session, payload: WorkflowDefinitionCreate, actor_id: UUID | None = None) -> WorkflowDefinition:
    existing_version = db.scalar(select(func.max(WorkflowDefinition.version)).where(WorkflowDefinition.code == payload.code))
    version = 1 if existing_version is None else existing_version + 1
    definition = WorkflowDefinition(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        entity_type=payload.entity_type,
        version=version,
        is_active=True,
        is_published=False,
    )
    db.add(definition)
    db.flush()
    write_audit(db, "WORKFLOW_DEFINITION_CREATED", "WorkflowDefinition", definition.id, actor_id=actor_id, new_data={"code": definition.code, "version": definition.version})
    return definition


def create_workflow_version(db: Session, source_definition_id: UUID, actor_id: UUID | None = None) -> WorkflowDefinition:
    source = get_definition_or_404(db, source_definition_id)
    latest = db.scalar(select(func.max(WorkflowDefinition.version)).where(WorkflowDefinition.code == source.code)) or source.version
    definition = WorkflowDefinition(
        code=source.code,
        name=source.name,
        description=source.description,
        entity_type=source.entity_type,
        version=latest + 1,
        is_active=True,
        is_published=False,
    )
    db.add(definition)
    db.flush()

    state_by_old_id: dict[UUID, WorkflowState] = {}
    for state in sorted(source.states, key=lambda item: item.sort_order):
        cloned = WorkflowState(
            workflow_definition_id=definition.id,
            code=state.code,
            name=state.name,
            description=state.description,
            state_type=state.state_type,
            sort_order=state.sort_order,
            is_initial=state.is_initial,
            is_terminal=state.is_terminal,
            color_token=state.color_token,
            icon=state.icon,
            is_active=state.is_active,
        )
        db.add(cloned)
        db.flush()
        state_by_old_id[state.id] = cloned

    for transition in sorted(source.transitions, key=lambda item: item.sort_order):
        db.add(
            WorkflowTransition(
                workflow_definition_id=definition.id,
                code=transition.code,
                name=transition.name,
                description=transition.description,
                from_state_id=state_by_old_id[transition.from_state_id].id,
                to_state_id=state_by_old_id[transition.to_state_id].id,
                permission_code=transition.permission_code,
                requires_comment=transition.requires_comment,
                requires_reason=transition.requires_reason,
                requires_attachment=transition.requires_attachment,
                confirmation_required=transition.confirmation_required,
                sort_order=transition.sort_order,
                is_active=transition.is_active,
                configuration_json=transition.configuration_json,
            )
        )

    db.flush()
    write_audit(db, "WORKFLOW_DEFINITION_CREATED", "WorkflowDefinition", definition.id, actor_id=actor_id, new_data={"code": definition.code, "version": definition.version, "source_definition_id": str(source.id)})
    return definition


def update_workflow_definition(db: Session, definition_id: UUID, payload: WorkflowDefinitionUpdate, actor_id: UUID | None = None) -> WorkflowDefinition:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    values = payload.model_dump(exclude_unset=True)
    old = {key: getattr(definition, key) for key in values}
    for key, value in values.items():
        setattr(definition, key, value)
    write_audit(db, "WORKFLOW_DEFINITION_UPDATED", "WorkflowDefinition", definition.id, actor_id=actor_id, old_data=old, new_data=values)
    db.flush()
    return definition


def add_workflow_state(db: Session, definition_id: UUID, payload: WorkflowStateCreate) -> WorkflowState:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    if payload.is_initial:
        ensure_no_other_initial_state(db.scalars(select(WorkflowState).where(WorkflowState.workflow_definition_id == definition.id)).all())
    state = WorkflowState(workflow_definition_id=definition.id, **payload.model_dump())
    db.add(state)
    db.flush()
    return state


def update_workflow_state(db: Session, definition_id: UUID, state_id: UUID, payload: WorkflowStateUpdate) -> WorkflowState:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    state = db.scalar(select(WorkflowState).where(WorkflowState.workflow_definition_id == definition.id, WorkflowState.id == state_id))
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow state not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_initial"):
        ensure_no_other_initial_state(
            db.scalars(
                select(WorkflowState).where(
                    WorkflowState.workflow_definition_id == definition.id,
                    WorkflowState.id != state_id,
                )
            ).all()
        )
    for key, value in values.items():
        setattr(state, key, value)
    db.flush()
    return state


def ensure_no_other_initial_state(states: Iterable[WorkflowState]) -> None:
    if any(state.is_initial and state.is_active for state in states):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow definition already has an initial state")


def add_workflow_transition(db: Session, definition_id: UUID, payload: WorkflowTransitionCreate) -> WorkflowTransition:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    validate_transition_states(db, definition.id, payload.from_state_id, payload.to_state_id)
    validate_configuration(payload.configuration_json)
    transition = WorkflowTransition(workflow_definition_id=definition.id, **payload.model_dump())
    db.add(transition)
    db.flush()
    return transition


def update_workflow_transition(db: Session, definition_id: UUID, transition_id: UUID, payload: WorkflowTransitionUpdate) -> WorkflowTransition:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    transition = db.scalar(select(WorkflowTransition).where(WorkflowTransition.workflow_definition_id == definition.id, WorkflowTransition.id == transition_id))
    if transition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow transition not found")
    values = payload.model_dump(exclude_unset=True)
    from_state_id = values.get("from_state_id", transition.from_state_id)
    to_state_id = values.get("to_state_id", transition.to_state_id)
    validate_transition_states(db, definition.id, from_state_id, to_state_id)
    validate_configuration(values.get("configuration_json", transition.configuration_json))
    for key, value in values.items():
        setattr(transition, key, value)
    db.flush()
    return transition


def validate_transition_states(db: Session, definition_id: UUID, from_state_id: UUID, to_state_id: UUID) -> None:
    state_ids = set(db.scalars(select(WorkflowState.id).where(WorkflowState.workflow_definition_id == definition_id)).all())
    if from_state_id not in state_ids or to_state_id not in state_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition states must belong to workflow definition")


def add_sla_policy(db: Session, definition_id: UUID, payload: WorkflowSlaPolicyCreate) -> WorkflowSlaPolicy:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    validate_sla_references(db, definition.id, payload.state_id, payload.transition_id)
    policy = WorkflowSlaPolicy(workflow_definition_id=definition.id, **payload.model_dump())
    db.add(policy)
    db.flush()
    return policy


def update_sla_policy(db: Session, definition_id: UUID, sla_id: UUID, payload: WorkflowSlaPolicyUpdate) -> WorkflowSlaPolicy:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    policy = db.scalar(select(WorkflowSlaPolicy).where(WorkflowSlaPolicy.workflow_definition_id == definition.id, WorkflowSlaPolicy.id == sla_id))
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow SLA policy not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    db.flush()
    return policy


def validate_sla_references(db: Session, definition_id: UUID, state_id: UUID | None, transition_id: UUID | None) -> None:
    if state_id is not None and db.scalar(select(WorkflowState.id).where(WorkflowState.workflow_definition_id == definition_id, WorkflowState.id == state_id)) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SLA state must belong to workflow definition")
    if transition_id is not None and db.scalar(select(WorkflowTransition.id).where(WorkflowTransition.workflow_definition_id == definition_id, WorkflowTransition.id == transition_id)) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SLA transition must belong to workflow definition")


def publish_workflow_definition(db: Session, definition_id: UUID, actor_id: UUID | None = None) -> WorkflowDefinition:
    definition = get_definition_or_404(db, definition_id)
    ensure_draft(definition)
    validate_publishable_definition(db, definition)
    definition.is_published = True
    definition.published_at = utc_now()
    write_audit(db, "WORKFLOW_DEFINITION_PUBLISHED", "WorkflowDefinition", definition.id, actor_id=actor_id, new_data={"code": definition.code, "version": definition.version})
    db.flush()
    return definition


def deactivate_workflow_definition(db: Session, definition_id: UUID, actor_id: UUID | None = None) -> WorkflowDefinition:
    definition = get_definition_or_404(db, definition_id)
    definition.is_active = False
    write_audit(db, "WORKFLOW_DEFINITION_DEACTIVATED", "WorkflowDefinition", definition.id, actor_id=actor_id, new_data={"code": definition.code, "version": definition.version})
    db.flush()
    return definition


def validate_publishable_definition(db: Session, definition: WorkflowDefinition) -> None:
    active_states = list(db.scalars(select(WorkflowState).where(WorkflowState.workflow_definition_id == definition.id, WorkflowState.is_active.is_(True))).all())
    initial_states = [state for state in active_states if state.is_initial]
    if len(initial_states) != 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow must have exactly one initial state")
    state_ids = {state.id for state in active_states}
    if not state_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow must contain states")

    transitions = list(db.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_definition_id == definition.id)).all())
    for transition in transitions:
        if not transition.is_active:
            continue
        if transition.from_state_id not in state_ids or transition.to_state_id not in state_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active transitions must connect active workflow states")
        validate_configuration(transition.configuration_json)
        if transition.permission_code is not None:
            permission = db.scalar(select(Permission).where(Permission.code == transition.permission_code, Permission.is_active.is_(True)))
            if permission is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition references an unknown permission")

    reachable = reachable_state_ids(initial_states[0].id, transitions)
    unreachable = state_ids - reachable
    if unreachable:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow contains unreachable active states")


def reachable_state_ids(initial_state_id: UUID, transitions: Iterable[WorkflowTransition]) -> set[UUID]:
    reachable = {initial_state_id}
    changed = True
    while changed:
        changed = False
        for transition in transitions:
            if not transition.is_active:
                continue
            if transition.from_state_id in reachable and transition.to_state_id not in reachable:
                reachable.add(transition.to_state_id)
                changed = True
    return reachable
