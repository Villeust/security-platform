from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from statistics import median
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.api.deps import get_current_permissions, require_csrf, require_permission
from app.core.config import settings
from app.core.query import validate_search, validate_sort
from app.db.session import get_db
from app.models.admin import AdminAuditLog, Permission, User
from app.models.reference_data import utc_now
from app.models.requests import ContractorRequest
from app.models.workflow import (
    DomainEventOutbox,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowSlaPolicy,
    WorkflowSlaTimer,
    WorkflowState,
    WorkflowTransition,
    WorkflowTransitionExecution,
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
from app.schemas.workflow_center import (
    OutboxMonitorResponse,
    PlatformHealthItem,
    PlatformHealthResponse,
    ProcessAuditItem,
    ProcessAuditResponse,
    SlaCenterResponse,
    WorkflowDashboardActivity,
    WorkflowDashboardResponse,
    WorkflowDefinitionDetailResponse,
    WorkflowDefinitionListItem,
    WorkflowDefinitionListResponse,
    WorkflowExecutionDto,
    WorkflowInstanceDetailResponse,
    WorkflowInstanceListItem,
    WorkflowInstanceListResponse,
    WorkflowMetric,
    WorkflowOutboxDto,
    WorkflowSearchResponse,
    WorkflowSearchResult,
    WorkflowSlaPolicyDto,
    WorkflowSlaTimerDto,
    WorkflowStateDto,
    WorkflowStatisticsResponse,
    WorkflowTransitionDto,
    WorkflowValidationIssue,
    WorkflowValidationResponse,
    WorkflowVersionDiffResponse,
    WorkflowVersionItem,
    WorkflowVersionListResponse,
)
from app.services.contractor_request_workflow import CONTRACTOR_REQUEST_ENTITY_TYPE, CONTRACTOR_REQUEST_WORKFLOW_CODE
from app.services.workflow_definition_service import (
    add_sla_policy,
    add_workflow_state,
    add_workflow_transition,
    create_workflow_definition,
    create_workflow_version,
    deactivate_workflow_definition,
    publish_workflow_definition,
    update_sla_policy,
    update_workflow_definition,
    update_workflow_state,
    update_workflow_transition,
)
from app.scripts.platform_doctor import ERROR, WARNING, run_doctor

router = APIRouter(prefix="/admin/workflow-center", tags=["admin workflow center"], dependencies=[Depends(require_csrf)])


def duration_label(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if minutes < 60:
        return f"{minutes} мин"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} ч" + (f" {mins} мин" if mins else "")
    days, rem_hours = divmod(hours, 24)
    return f"{days} д" + (f" {rem_hours} ч" if rem_hours else "")


def format_duration(delta: timedelta | None) -> str:
    if delta is None:
        return "нет данных"
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} сек"
    minutes = seconds // 60
    return duration_label(minutes) or "нет данных"


def business_identifier(entity_type: str, entity_id: UUID, request_number: str | None = None) -> str:
    if entity_type == CONTRACTOR_REQUEST_ENTITY_TYPE and request_number:
        return request_number
    return str(entity_id)


def workflow_state_map(definition: WorkflowDefinition) -> dict[UUID, WorkflowState]:
    return {state.id: state for state in definition.states}


def serialize_state(state: WorkflowState, transitions: list[WorkflowTransition]) -> WorkflowStateDto:
    incoming = sum(1 for transition in transitions if transition.to_state_id == state.id)
    outgoing = sum(1 for transition in transitions if transition.from_state_id == state.id)
    return WorkflowStateDto(
        id=state.id,
        code=state.code,
        name=state.name,
        description=state.description,
        state_type=state.state_type.value,
        sort_order=state.sort_order,
        is_initial=state.is_initial,
        is_terminal=state.is_terminal,
        color_token=state.color_token,
        icon=state.icon,
        is_active=state.is_active,
        incoming_count=incoming,
        outgoing_count=outgoing,
    )


def serialize_transition(transition: WorkflowTransition, states: dict[UUID, WorkflowState]) -> WorkflowTransitionDto:
    return WorkflowTransitionDto(
        id=transition.id,
        code=transition.code,
        name=transition.name,
        description=transition.description,
        from_state_id=transition.from_state_id,
        to_state_id=transition.to_state_id,
        from_state_code=states.get(transition.from_state_id).code if states.get(transition.from_state_id) else None,
        to_state_code=states.get(transition.to_state_id).code if states.get(transition.to_state_id) else None,
        permission_code=transition.permission_code,
        requires_comment=transition.requires_comment,
        requires_reason=transition.requires_reason,
        requires_attachment=transition.requires_attachment,
        confirmation_required=transition.confirmation_required,
        sort_order=transition.sort_order,
        is_active=transition.is_active,
        configuration_json=transition.configuration_json,
    )


def serialize_sla(policy: WorkflowSlaPolicy, states: dict[UUID, WorkflowState], transitions: dict[UUID, WorkflowTransition]) -> WorkflowSlaPolicyDto:
    state = states.get(policy.state_id) if policy.state_id else None
    transition = transitions.get(policy.transition_id) if policy.transition_id else None
    return WorkflowSlaPolicyDto(
        id=policy.id,
        code=policy.code,
        name=policy.name,
        state_id=policy.state_id,
        state_code=state.code if state else None,
        transition_id=policy.transition_id,
        transition_code=transition.code if transition else None,
        duration_minutes=policy.duration_minutes,
        duration_label=duration_label(policy.duration_minutes) or "",
        warning_before_minutes=policy.warning_before_minutes,
        warning_label=duration_label(policy.warning_before_minutes),
        business_calendar_code=policy.business_calendar_code or "24/7",
        severity=policy.severity,
        is_active=policy.is_active,
    )


def definition_counts(db: Session) -> dict[UUID, dict[str, int]]:
    state_rows = dict(db.execute(select(WorkflowState.workflow_definition_id, func.count()).group_by(WorkflowState.workflow_definition_id)).all())
    transition_rows = dict(db.execute(select(WorkflowTransition.workflow_definition_id, func.count()).group_by(WorkflowTransition.workflow_definition_id)).all())
    instance_rows = dict(db.execute(select(WorkflowInstance.workflow_definition_id, func.count()).group_by(WorkflowInstance.workflow_definition_id)).all())
    ids = set(state_rows) | set(transition_rows) | set(instance_rows)
    return {
        item_id: {
            "states": int(state_rows.get(item_id, 0)),
            "transitions": int(transition_rows.get(item_id, 0)),
            "instances": int(instance_rows.get(item_id, 0)),
        }
        for item_id in ids
    }


def serialize_definition_list_item(definition: WorkflowDefinition, counts: dict[UUID, dict[str, int]]) -> WorkflowDefinitionListItem:
    item_counts = counts.get(definition.id, {})
    return WorkflowDefinitionListItem(
        id=definition.id,
        code=definition.code,
        name=definition.name,
        description=definition.description,
        entity_type=definition.entity_type,
        version=definition.version,
        is_published=definition.is_published,
        is_active=definition.is_active,
        states_count=item_counts.get("states", 0),
        transitions_count=item_counts.get("transitions", 0),
        instances_count=item_counts.get("instances", 0),
        created_at=definition.created_at,
        updated_at=definition.updated_at,
        published_at=definition.published_at,
    )


def get_definition(db: Session, definition_id: UUID) -> WorkflowDefinition:
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
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow definition not found")
    return definition


def ensure_workflow_center_mutation_allowed(definition: WorkflowDefinition) -> None:
    if definition.code == CONTRACTOR_REQUEST_WORKFLOW_CODE and definition.version == 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contractor Request workflow v1 is managed by the Contractor Requests module",
        )


def validation_for_definition(db: Session, definition: WorkflowDefinition) -> WorkflowValidationResponse:
    states = list(definition.states)
    transitions = list(definition.transitions)
    state_by_id = {state.id: state for state in states}
    permissions = set(db.scalars(select(Permission.code).where(Permission.is_active.is_(True))).all())
    errors: list[WorkflowValidationIssue] = []
    warnings: list[WorkflowValidationIssue] = []
    info: list[WorkflowValidationIssue] = []

    initial = [state for state in states if state.is_active and state.is_initial]
    if len(initial) == 1:
        info.append(WorkflowValidationIssue(code="initial_state", severity="info", message="Начальное состояние задано", target_type="state", target_code=initial[0].code))
    else:
        errors.append(WorkflowValidationIssue(code="initial_state", severity="error", message="Должно быть ровно одно активное начальное состояние"))

    active_state_ids = {state.id for state in states if state.is_active}
    active_transitions = [transition for transition in transitions if transition.is_active]
    reachable = set()
    if initial:
        reachable.add(initial[0].id)
        changed = True
        while changed:
            changed = False
            for transition in active_transitions:
                if transition.from_state_id in reachable and transition.to_state_id not in reachable:
                    reachable.add(transition.to_state_id)
                    changed = True
    dead_states = [state.code for state in states if state.is_active and state.id not in reachable]
    if dead_states:
        errors.append(WorkflowValidationIssue(code="dead_states", severity="error", message=f"Недостижимые состояния: {', '.join(dead_states)}"))
    else:
        info.append(WorkflowValidationIssue(code="reachability", severity="info", message="Все активные состояния достижимы"))

    terminal = [state for state in states if state.is_active and state.is_terminal]
    if terminal:
        info.append(WorkflowValidationIssue(code="terminal_states", severity="info", message=f"Терминальных состояний: {len(terminal)}"))
    else:
        warnings.append(WorkflowValidationIssue(code="terminal_states", severity="warning", message="Нет терминальных состояний"))

    state_codes = Counter(state.code for state in states)
    transition_codes = Counter(transition.code for transition in transitions)
    duplicates = [code for code, count in {**state_codes, **transition_codes}.items() if count > 1]
    if duplicates:
        errors.append(WorkflowValidationIssue(code="duplicate_codes", severity="error", message=f"Дубли кодов: {', '.join(duplicates)}"))
    else:
        info.append(WorkflowValidationIssue(code="duplicate_codes", severity="info", message="Дубли кодов не найдены"))

    dead_transitions = [
        transition.code
        for transition in active_transitions
        if transition.from_state_id not in active_state_ids or transition.to_state_id not in active_state_ids
    ]
    if dead_transitions:
        errors.append(WorkflowValidationIssue(code="dead_transitions", severity="error", message=f"Переходы с неактивными состояниями: {', '.join(dead_transitions)}"))
    else:
        info.append(WorkflowValidationIssue(code="dead_transitions", severity="info", message="Мёртвые переходы не найдены"))

    missing_permissions = sorted({transition.permission_code for transition in active_transitions if transition.permission_code and transition.permission_code not in permissions})
    if missing_permissions:
        errors.append(WorkflowValidationIssue(code="permission_validation", severity="error", message=f"Неизвестные разрешения: {', '.join(missing_permissions)}"))
    else:
        info.append(WorkflowValidationIssue(code="permission_validation", severity="info", message="Разрешения переходов валидны"))

    unsafe = [transition.code for transition in transitions if transition.configuration_json and not isinstance(transition.configuration_json, dict)]
    if unsafe:
        errors.append(WorkflowValidationIssue(code="unsafe_configuration", severity="error", message=f"Небезопасная конфигурация: {', '.join(unsafe)}"))
    else:
        info.append(WorkflowValidationIssue(code="unsafe_configuration", severity="info", message="Небезопасная конфигурация не найдена"))

    invalid_sla = [policy.code for policy in definition.sla_policies if (policy.state_id and policy.state_id not in state_by_id)]
    if invalid_sla:
        errors.append(WorkflowValidationIssue(code="sla_validation", severity="error", message=f"SLA с неверными ссылками: {', '.join(invalid_sla)}"))
    else:
        info.append(WorkflowValidationIssue(code="sla_validation", severity="info", message="SLA ссылки валидны"))

    if definition.is_published:
        info.append(WorkflowValidationIssue(code="published_rules", severity="info", message="Версия опубликована и доступна только для чтения"))
    elif active_state_ids:
        warnings.append(WorkflowValidationIssue(code="published_rules", severity="warning", message="Черновик не опубликован"))

    status = "error" if errors else "warning" if warnings else "ok"
    return WorkflowValidationResponse(status=status, errors=errors, warnings=warnings, info=info)


def serialize_definition_detail(db: Session, definition: WorkflowDefinition) -> WorkflowDefinitionDetailResponse:
    states = workflow_state_map(definition)
    transitions_by_id = {transition.id: transition for transition in definition.transitions}
    counts = definition_counts(db)
    base = serialize_definition_list_item(definition, counts).model_dump()
    created = db.scalar(select(AdminAuditLog.actor_id).where(AdminAuditLog.entity_id == definition.id, AdminAuditLog.action == "WORKFLOW_DEFINITION_CREATED").order_by(AdminAuditLog.created_at.asc()))
    published = db.scalar(select(AdminAuditLog.actor_id).where(AdminAuditLog.entity_id == definition.id, AdminAuditLog.action == "WORKFLOW_DEFINITION_PUBLISHED").order_by(AdminAuditLog.created_at.desc()))
    return WorkflowDefinitionDetailResponse(
        **base,
        states=[serialize_state(state, definition.transitions) for state in sorted(definition.states, key=lambda item: item.sort_order)],
        transitions=[serialize_transition(item, states) for item in sorted(definition.transitions, key=lambda item: item.sort_order)],
        sla_policies=[serialize_sla(item, states, transitions_by_id) for item in definition.sla_policies],
        validation=validation_for_definition(db, definition),
        created_by=created,
        published_by=published,
    )


def serialize_instance(row) -> WorkflowInstanceListItem:
    instance, definition, state, request_number = row
    return WorkflowInstanceListItem(
        id=instance.id,
        workflow_definition_id=instance.workflow_definition_id,
        workflow_code=definition.code,
        workflow_name=definition.name,
        workflow_version=instance.workflow_version,
        entity_type=instance.entity_type,
        entity_id=instance.entity_id,
        business_identifier=business_identifier(instance.entity_type, instance.entity_id, request_number),
        current_state=state.name,
        current_state_code=state.code,
        started_at=instance.started_at,
        updated_at=instance.updated_at,
        completed_at=instance.completed_at,
        cancelled_at=instance.cancelled_at,
        lock_version=instance.lock_version,
    )


def instance_query():
    return (
        select(WorkflowInstance, WorkflowDefinition, WorkflowState, ContractorRequest.request_number)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowInstance.workflow_definition_id)
        .join(WorkflowState, WorkflowState.id == WorkflowInstance.current_state_id)
        .outerjoin(ContractorRequest, ContractorRequest.id == WorkflowInstance.entity_id)
    )


def serialize_timer(timer: WorkflowSlaTimer, policy: WorkflowSlaPolicy | None = None) -> WorkflowSlaTimerDto:
    return WorkflowSlaTimerDto(
        id=timer.id,
        policy_code=policy.code if policy else None,
        policy_name=policy.name if policy else None,
        started_at=timer.started_at,
        due_at=timer.due_at,
        warning_at=timer.warning_at,
        completed_at=timer.completed_at,
        breached_at=timer.breached_at,
        status=timer.status.value,
    )


def serialize_outbox(event: DomainEventOutbox, business_id: str | None = None) -> WorkflowOutboxDto:
    correlation_id = event.correlation_id
    if isinstance(event.payload, dict):
        correlation_id = correlation_id or event.payload.get("correlation_id")
    return WorkflowOutboxDto(
        id=event.id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        business_identifier=business_id or str(event.aggregate_id),
        created_at=event.created_at,
        processed_at=event.processed_at,
        status=event.status.value,
        attempts=event.attempts,
        correlation_id=correlation_id,
        last_error=event.last_error,
    )


def metric(key: str, label: str, value: int | float | str, tone: str = "healthy", target: str | None = None) -> WorkflowMetric:
    return WorkflowMetric(key=key, label=label, value=value, tone=tone, target=target)


@router.get("/dashboard", response_model=WorkflowDashboardResponse)
def workflow_dashboard(db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.instances.view"))) -> WorkflowDashboardResponse:
    today = utc_now().date()
    definitions = db.scalar(select(func.count()).select_from(WorkflowDefinition)) or 0
    published = db.scalar(select(func.count()).select_from(WorkflowDefinition).where(WorkflowDefinition.is_published.is_(True))) or 0
    drafts = db.scalar(select(func.count()).select_from(WorkflowDefinition).where(WorkflowDefinition.is_published.is_(False))) or 0
    instances = db.scalar(select(func.count()).select_from(WorkflowInstance)) or 0
    active_instances = db.scalar(select(func.count()).select_from(WorkflowInstance).where(WorkflowInstance.completed_at.is_(None), WorkflowInstance.cancelled_at.is_(None))) or 0
    completed_today = db.scalar(select(func.count()).select_from(WorkflowInstance).where(func.date(WorkflowInstance.completed_at) == str(today))) or 0
    sla_violations = db.scalar(select(func.count()).select_from(WorkflowSlaTimer).where(WorkflowSlaTimer.breached_at.is_not(None))) or 0
    pending_outbox = db.scalar(select(func.count()).select_from(DomainEventOutbox).where(DomainEventOutbox.status == "PENDING")) or 0
    failed_outbox = db.scalar(select(func.count()).select_from(DomainEventOutbox).where(DomainEventOutbox.status == "FAILED")) or 0
    durations = [
        item.completed_at - item.started_at
        for item in db.scalars(select(WorkflowInstance).where(WorkflowInstance.completed_at.is_not(None))).all()
        if item.completed_at and item.started_at
    ]
    avg_duration = format_duration(sum(durations, timedelta()) / len(durations) if durations else None)
    health_score = max(0, 100 - int(sla_violations) * 5 - int(failed_outbox) * 10)
    activities = [
        WorkflowDashboardActivity(
            id=item.id,
            action=item.action,
            workflow_code=(item.new_data or {}).get("code") if isinstance(item.new_data, dict) else None,
            workflow_version=(item.new_data or {}).get("version") if isinstance(item.new_data, dict) else None,
            actor_id=item.actor_id,
            created_at=item.created_at,
        )
        for item in db.scalars(select(AdminAuditLog).where(AdminAuditLog.action.like("WORKFLOW_%")).order_by(desc(AdminAuditLog.created_at)).limit(10)).all()
    ]
    return WorkflowDashboardResponse(
        health_score=health_score,
        metrics=[
            metric("definitions", "Определения процессов", definitions, target="/admin/workflow-center/definitions"),
            metric("published", "Опубликованные версии", published, target="/admin/workflow-center/versions"),
            metric("drafts", "Черновики", drafts, "attention" if drafts else "healthy", "/admin/workflow-center/versions"),
            metric("instances", "Экземпляры процессов", instances, target="/admin/workflow-center/instances"),
            metric("active_instances", "Активные экземпляры", active_instances, target="/admin/workflow-center/instances"),
            metric("completed_today", "Завершено сегодня", completed_today, target="/admin/workflow-center/instances"),
            metric("sla_violations", "Нарушения SLA", sla_violations, "error" if sla_violations else "healthy", "/admin/workflow-center/sla"),
            metric("pending_outbox", "Ожидающие события", pending_outbox, "attention" if pending_outbox else "healthy", "/admin/workflow-center/outbox"),
            metric("failed_outbox", "Ошибки событий", failed_outbox, "error" if failed_outbox else "healthy", "/admin/workflow-center/outbox"),
            metric("avg_transition", "Средняя длительность перехода", "нет данных"),
            metric("avg_workflow", "Средняя длительность процесса", avg_duration),
            metric("health", "Индекс состояния", f"{health_score}%", "error" if health_score < 70 else "attention" if health_score < 90 else "healthy", "/admin/workflow-center/health"),
        ],
        recent_activity=activities,
    )


@router.get("/definitions", response_model=WorkflowDefinitionListResponse)
def list_definitions(
    search: str | None = Query(default=None, max_length=settings.max_search_length),
    entity_type: str | None = None,
    published: bool | None = None,
    active: bool | None = None,
    sort: str = "updated_at",
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("workflows.view")),
) -> WorkflowDefinitionListResponse:
    search = validate_search(search)
    query = select(WorkflowDefinition)
    count_query = select(func.count()).select_from(WorkflowDefinition)
    filters = []
    if search:
        pattern = f"%{search}%"
        filters.append(or_(WorkflowDefinition.code.ilike(pattern), WorkflowDefinition.name.ilike(pattern), WorkflowDefinition.entity_type.ilike(pattern)))
    if entity_type:
        filters.append(WorkflowDefinition.entity_type == entity_type)
    if published is not None:
        filters.append(WorkflowDefinition.is_published.is_(published))
    if active is not None:
        filters.append(WorkflowDefinition.is_active.is_(active))
    for item in filters:
        query = query.where(item)
        count_query = count_query.where(item)
    sort_column, sort_direction = validate_sort(
        sort,
        direction,
        {
            "updated_at": WorkflowDefinition.updated_at,
            "created_at": WorkflowDefinition.created_at,
            "code": WorkflowDefinition.code,
            "name": WorkflowDefinition.name,
            "version": WorkflowDefinition.version,
        },
    )
    query = query.order_by(desc(sort_column) if sort_direction == "desc" else sort_column).offset(skip).limit(limit)
    counts = definition_counts(db)
    return WorkflowDefinitionListResponse(
        items=[serialize_definition_list_item(item, counts) for item in db.scalars(query).all()],
        total=db.scalar(count_query) or 0,
        skip=skip,
        limit=limit,
    )


@router.post("/definitions", response_model=WorkflowDefinitionDetailResponse)
def create_definition(payload: WorkflowDefinitionCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("workflows.manage")), _: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    definition = create_workflow_definition(db, payload, actor_id=user.id)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition.id))


@router.get("/definitions/{definition_id}", response_model=WorkflowDefinitionDetailResponse)
def get_definition_detail(definition_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> WorkflowDefinitionDetailResponse:
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.patch("/definitions/{definition_id}", response_model=WorkflowDefinitionDetailResponse)
def update_definition(definition_id: UUID, payload: WorkflowDefinitionUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("workflows.manage")), _: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    definition = update_workflow_definition(db, definition_id, payload, actor_id=user.id)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition.id))


@router.post("/definitions/{definition_id}/versions", response_model=WorkflowDefinitionDetailResponse)
def create_version(definition_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_permission("workflows.manage")), _: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    definition = create_workflow_version(db, definition_id, actor_id=user.id)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition.id))


@router.post("/definitions/{definition_id}/publish", response_model=WorkflowDefinitionDetailResponse)
def publish_definition(definition_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_permission("workflows.publish")), _: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    definition = publish_workflow_definition(db, definition_id, actor_id=user.id)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition.id))


@router.post("/definitions/{definition_id}/deactivate", response_model=WorkflowDefinitionDetailResponse)
def deactivate_definition(definition_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_permission("workflows.manage")), _: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    definition = deactivate_workflow_definition(db, definition_id, actor_id=user.id)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition.id))


@router.post("/definitions/{definition_id}/states", response_model=WorkflowDefinitionDetailResponse)
def create_state(definition_id: UUID, payload: WorkflowStateCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.manage")), __: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    add_workflow_state(db, definition_id, payload)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.patch("/definitions/{definition_id}/states/{state_id}", response_model=WorkflowDefinitionDetailResponse)
def patch_state(definition_id: UUID, state_id: UUID, payload: WorkflowStateUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.manage")), __: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    update_workflow_state(db, definition_id, state_id, payload)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.post("/definitions/{definition_id}/transitions", response_model=WorkflowDefinitionDetailResponse)
def create_transition(definition_id: UUID, payload: WorkflowTransitionCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.manage")), __: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    add_workflow_transition(db, definition_id, payload)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.patch("/definitions/{definition_id}/transitions/{transition_id}", response_model=WorkflowDefinitionDetailResponse)
def patch_transition(definition_id: UUID, transition_id: UUID, payload: WorkflowTransitionUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.manage")), __: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    update_workflow_transition(db, definition_id, transition_id, payload)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.post("/definitions/{definition_id}/sla", response_model=WorkflowDefinitionDetailResponse)
def create_sla(definition_id: UUID, payload: WorkflowSlaPolicyCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.sla.manage")), __: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    add_sla_policy(db, definition_id, payload)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.patch("/definitions/{definition_id}/sla/{sla_id}", response_model=WorkflowDefinitionDetailResponse)
def patch_sla(definition_id: UUID, sla_id: UUID, payload: WorkflowSlaPolicyUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.sla.manage")), __: None = Depends(require_csrf)) -> WorkflowDefinitionDetailResponse:
    ensure_workflow_center_mutation_allowed(get_definition(db, definition_id))
    update_sla_policy(db, definition_id, sla_id, payload)
    db.commit()
    return serialize_definition_detail(db, get_definition(db, definition_id))


@router.get("/definitions/{definition_id}/validation", response_model=WorkflowValidationResponse)
def validate_definition(definition_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> WorkflowValidationResponse:
    return validation_for_definition(db, get_definition(db, definition_id))


@router.get("/versions", response_model=WorkflowVersionListResponse)
def list_versions(code: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> WorkflowVersionListResponse:
    query = select(WorkflowDefinition).order_by(WorkflowDefinition.code, desc(WorkflowDefinition.version))
    if code:
        query = query.where(WorkflowDefinition.code == code)
    counts = definition_counts(db)
    items = []
    for definition in db.scalars(query).all():
        created_by = db.scalar(select(AdminAuditLog.actor_id).where(AdminAuditLog.entity_id == definition.id, AdminAuditLog.action == "WORKFLOW_DEFINITION_CREATED").order_by(AdminAuditLog.created_at.asc()))
        items.append(
            WorkflowVersionItem(
                id=definition.id,
                code=definition.code,
                version=definition.version,
                status="published" if definition.is_published else "draft",
                created_by=created_by,
                created_at=definition.created_at,
                published_at=definition.published_at,
                comment=definition.description,
                instances_count=counts.get(definition.id, {}).get("instances", 0),
                is_active=definition.is_active,
                is_published=definition.is_published,
            )
        )
    return WorkflowVersionListResponse(items=items, total=len(items))


@router.get("/versions/diff", response_model=WorkflowVersionDiffResponse)
def version_diff(source_id: UUID, target_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> WorkflowVersionDiffResponse:
    source = get_definition(db, source_id)
    target = get_definition(db, target_id)
    source_states = {state.code: state for state in source.states}
    target_states = {state.code: state for state in target.states}
    source_transitions = {transition.code: transition for transition in source.transitions}
    target_transitions = {transition.code: transition for transition in target.transitions}
    permission_changes = [
        code
        for code in sorted(set(source_transitions) & set(target_transitions))
        if source_transitions[code].permission_code != target_transitions[code].permission_code
    ]
    metadata_changes = [
        field
        for field in ("name", "description", "entity_type", "is_active", "is_published")
        if getattr(source, field) != getattr(target, field)
    ]
    return WorkflowVersionDiffResponse(
        source_version=source.version,
        target_version=target.version,
        added_states=sorted(set(target_states) - set(source_states)),
        removed_states=sorted(set(source_states) - set(target_states)),
        added_transitions=sorted(set(target_transitions) - set(source_transitions)),
        removed_transitions=sorted(set(source_transitions) - set(target_transitions)),
        permission_changes=permission_changes,
        sla_changes=sorted({item.code for item in target.sla_policies} ^ {item.code for item in source.sla_policies}),
        metadata_changes=metadata_changes,
    )


@router.get("/instances", response_model=WorkflowInstanceListResponse)
def list_instances(
    search: str | None = Query(default=None, max_length=settings.max_search_length),
    workflow_code: str | None = None,
    state_code: str | None = None,
    active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("workflows.instances.view")),
) -> WorkflowInstanceListResponse:
    search = validate_search(search)
    query = instance_query()
    count_query = select(func.count()).select_from(WorkflowInstance).join(WorkflowDefinition).join(WorkflowState, WorkflowState.id == WorkflowInstance.current_state_id).outerjoin(ContractorRequest, ContractorRequest.id == WorkflowInstance.entity_id)
    filters = []
    if search:
        pattern = f"%{search}%"
        filters.append(or_(WorkflowDefinition.code.ilike(pattern), WorkflowState.code.ilike(pattern), ContractorRequest.request_number.ilike(pattern)))
    if workflow_code:
        filters.append(WorkflowDefinition.code == workflow_code)
    if state_code:
        filters.append(WorkflowState.code == state_code)
    if active is not None:
        filters.append(WorkflowInstance.completed_at.is_(None) if active else WorkflowInstance.completed_at.is_not(None))
    for item in filters:
        query = query.where(item)
        count_query = count_query.where(item)
    rows = db.execute(query.order_by(desc(WorkflowInstance.updated_at)).offset(skip).limit(limit)).all()
    return WorkflowInstanceListResponse(items=[serialize_instance(row) for row in rows], total=db.scalar(count_query) or 0, skip=skip, limit=limit)


@router.get("/instances/{instance_id}", response_model=WorkflowInstanceDetailResponse)
def get_instance(instance_id: UUID, permissions: set[str] = Depends(get_current_permissions), db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.instances.view"))) -> WorkflowInstanceDetailResponse:
    row = db.execute(instance_query().where(WorkflowInstance.id == instance_id)).first()
    if row is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow instance not found")
    base = serialize_instance(row)
    executions = []
    from_state_alias = aliased(WorkflowState)
    to_state_alias = aliased(WorkflowState)
    for execution, transition, from_state, to_state in db.execute(
        select(WorkflowTransitionExecution, WorkflowTransition, from_state_alias, to_state_alias)
        .join(WorkflowTransition, WorkflowTransition.id == WorkflowTransitionExecution.transition_id)
        .join(from_state_alias, from_state_alias.id == WorkflowTransitionExecution.from_state_id)
        .join(to_state_alias, to_state_alias.id == WorkflowTransitionExecution.to_state_id)
        .where(WorkflowTransitionExecution.workflow_instance_id == instance_id)
        .order_by(WorkflowTransitionExecution.created_at)
    ).all():
        executions.append(
            WorkflowExecutionDto(
                id=execution.id,
                transition_code=transition.code if transition else None,
                transition_name=transition.name if transition else None,
                from_state=from_state.code if from_state else None,
                to_state=to_state.code if to_state else None,
                actor_type=execution.actor_type.value,
                actor_id=execution.actor_id,
                comment=execution.comment,
                reason_code=execution.reason_code,
                created_at=execution.created_at,
                correlation_id=execution.correlation_id,
            )
        )
    timers = [serialize_timer(timer, policy) for timer, policy in db.execute(select(WorkflowSlaTimer, WorkflowSlaPolicy).join(WorkflowSlaPolicy, WorkflowSlaPolicy.id == WorkflowSlaTimer.sla_policy_id).where(WorkflowSlaTimer.workflow_instance_id == instance_id)).all()]
    outbox = [serialize_outbox(item, base.business_identifier) for item in db.scalars(select(DomainEventOutbox).where(DomainEventOutbox.aggregate_type == base.entity_type, DomainEventOutbox.aggregate_id == base.entity_id)).all()]
    return WorkflowInstanceDetailResponse(
        **base.model_dump(),
        executions=executions,
        sla_timers=timers,
        outbox_events=outbox,
        metadata={"business_identifier": base.business_identifier, "entity_type": base.entity_type},
        technical_details={"entity_id": str(base.entity_id), "definition_id": str(base.workflow_definition_id)} if "workflows.manage" in permissions else None,
    )


@router.get("/sla", response_model=SlaCenterResponse)
def sla_center(db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.sla.view"))) -> SlaCenterResponse:
    definitions = db.scalars(select(WorkflowDefinition).options(selectinload(WorkflowDefinition.states), selectinload(WorkflowDefinition.transitions), selectinload(WorkflowDefinition.sla_policies))).all()
    policies: list[WorkflowSlaPolicyDto] = []
    for definition in definitions:
        states = workflow_state_map(definition)
        transitions = {item.id: item for item in definition.transitions}
        policies.extend(serialize_sla(item, states, transitions) for item in definition.sla_policies)
    timers = [serialize_timer(timer, policy) for timer, policy in db.execute(select(WorkflowSlaTimer, WorkflowSlaPolicy).join(WorkflowSlaPolicy, WorkflowSlaPolicy.id == WorkflowSlaTimer.sla_policy_id)).all()]
    expired = sum(1 for item in timers if item.status == "BREACHED")
    warnings = sum(1 for item in timers if item.warning_at and not item.completed_at)
    return SlaCenterResponse(
        metrics=[
            metric("total", "Всего политик", len(policies)),
            metric("active", "Активные", sum(1 for item in policies if item.is_active)),
            metric("warnings", "Предупреждения", warnings, "attention" if warnings else "healthy"),
            metric("expired", "Просроченные таймеры", expired, "error" if expired else "healthy"),
        ],
        policies=policies,
        timers=timers,
        business_calendar_note="Бизнес-календари будут доступны в будущей версии. Сейчас используется календарь 24/7.",
    )


@router.get("/outbox", response_model=OutboxMonitorResponse)
def outbox_monitor(status: str | None = None, search: str | None = Query(default=None, max_length=settings.max_search_length), skip: int = Query(default=0, ge=0), limit: int = Query(default=50, le=200), db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.instances.view"))) -> OutboxMonitorResponse:
    search = validate_search(search)
    query = select(DomainEventOutbox).order_by(desc(DomainEventOutbox.created_at))
    count_query = select(func.count()).select_from(DomainEventOutbox)
    filters = []
    if status:
        filters.append(DomainEventOutbox.status == status)
    if search:
        filters.append(or_(DomainEventOutbox.event_type.ilike(f"%{search}%"), DomainEventOutbox.aggregate_type.ilike(f"%{search}%")))
    for item in filters:
        query = query.where(item)
        count_query = count_query.where(item)
    rows = db.scalars(query.offset(skip).limit(limit)).all()
    pending = db.scalar(select(func.count()).select_from(DomainEventOutbox).where(DomainEventOutbox.status == "PENDING")) or 0
    delivered = db.scalar(select(func.count()).select_from(DomainEventOutbox).where(DomainEventOutbox.status == "PROCESSED")) or 0
    failed = db.scalar(select(func.count()).select_from(DomainEventOutbox).where(DomainEventOutbox.status == "FAILED")) or 0
    retries = db.scalar(select(func.sum(DomainEventOutbox.attempts))) or 0
    return OutboxMonitorResponse(
        metrics=[
            metric("pending", "Ожидают обработки", pending, "attention" if pending else "healthy"),
            metric("delivered", "Доставлено", delivered),
            metric("failed", "С ошибкой", failed, "error" if failed else "healthy"),
            metric("retries", "Повторные попытки", retries, "attention" if retries else "healthy"),
            metric("dead_letter", "Мертвая очередь", failed, "error" if failed else "healthy"),
        ],
        items=[serialize_outbox(item) for item in rows],
        total=db.scalar(count_query) or 0,
        skip=skip,
        limit=limit,
    )


@router.get("/audit", response_model=ProcessAuditResponse)
def process_audit(action: str | None = None, workflow: str | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=50, le=200), db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> ProcessAuditResponse:
    query = select(AdminAuditLog).where(AdminAuditLog.action.like("WORKFLOW_%")).order_by(desc(AdminAuditLog.created_at))
    count_query = select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.action.like("WORKFLOW_%"))
    if action:
        query = query.where(AdminAuditLog.action == action)
        count_query = count_query.where(AdminAuditLog.action == action)
    if workflow:
        query = query.where(AdminAuditLog.new_data.contains({"code": workflow}))
    items = [
        ProcessAuditItem(
            id=item.id,
            action=item.action,
            workflow_code=(item.new_data or {}).get("code") if isinstance(item.new_data, dict) else None,
            workflow_version=(item.new_data or {}).get("version") if isinstance(item.new_data, dict) else None,
            actor_id=item.actor_id,
            actor_type=item.actor_type,
            created_at=item.created_at,
            safe_details=item.new_data,
        )
        for item in db.scalars(query.offset(skip).limit(limit)).all()
    ]
    return ProcessAuditResponse(items=items, total=db.scalar(count_query) or 0, skip=skip, limit=limit)


@router.get("/statistics", response_model=WorkflowStatisticsResponse)
def statistics(db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.instances.view"))) -> WorkflowStatisticsResponse:
    instances = db.scalars(select(WorkflowInstance)).all()
    completed = [item for item in instances if item.completed_at and item.started_at]
    durations = [item.completed_at - item.started_at for item in completed]
    cancelled = [item for item in instances if item.cancelled_at]
    executions = db.scalars(select(WorkflowTransitionExecution).order_by(WorkflowTransitionExecution.created_at)).all()
    transition_label = "нет данных" if not executions else "см. журнал переходов"
    sla_total = db.scalar(select(func.count()).select_from(WorkflowSlaTimer)) or 0
    sla_breached = db.scalar(select(func.count()).select_from(WorkflowSlaTimer).where(WorkflowSlaTimer.breached_at.is_not(None))) or 0
    return WorkflowStatisticsResponse(
        average_workflow_duration=format_duration(sum(durations, timedelta()) / len(durations) if durations else None),
        median_duration=format_duration(median(durations) if durations else None),
        fastest_transition=transition_label,
        slowest_transition=transition_label,
        average_completion_time=format_duration(sum(durations, timedelta()) / len(durations) if durations else None),
        completion_percent=round((len(completed) / len(instances) * 100), 2) if instances else 0,
        cancellation_percent=round((len(cancelled) / len(instances) * 100), 2) if instances else 0,
        sla_percent=round(((sla_total - sla_breached) / sla_total * 100), 2) if sla_total else 100,
    )


@router.get("/health", response_model=PlatformHealthResponse)
def platform_health(_: User = Depends(require_permission("workflows.instances.view"))) -> PlatformHealthResponse:
    report = run_doctor()
    data = report.to_dict()
    warnings: list[PlatformHealthItem] = []
    errors: list[PlatformHealthItem] = []
    status_by_section = {section["name"]: section["status"] for section in data["sections"]}
    for section in data["sections"]:
        for check in section["checks"]:
            item = PlatformHealthItem(name=f"{section['name']}: {check['name']}", status=check["status"], message=check["message"])
            if check["status"] == WARNING:
                warnings.append(item)
            elif check["status"] == ERROR:
                errors.append(item)
    return PlatformHealthResponse(
        health_score=data["health_percent"],
        backend_status="Healthy",
        database_status=status_by_section.get("Database", "unknown"),
        alembic_revision=next((check["details"].get("current") for section in data["sections"] if section["name"] == "Alembic" for check in section["checks"] if check["name"] == "current_revision"), None),
        workflow_engine=status_by_section.get("Workflow", "unknown"),
        workflow_definitions=status_by_section.get("Seed", "unknown"),
        workflow_instances=status_by_section.get("Workflow", "unknown"),
        rbac=status_by_section.get("RBAC", "unknown"),
        authentication=status_by_section.get("Auth", "unknown"),
        storage=status_by_section.get("Storage", "unknown"),
        smtp=next((check["status"] for section in data["sections"] if section["name"] == "Configuration" for check in section["checks"] if check["name"] == "SMTP"), "unknown"),
        ldap=next((check["status"] for section in data["sections"] if section["name"] == "Configuration" for check in section["checks"] if check["name"] == "LDAP"), "unknown"),
        adfs=next((check["status"] for section in data["sections"] if section["name"] == "Configuration" for check in section["checks"] if check["name"] == "ADFS"), "unknown"),
        warnings=warnings,
        errors=errors,
    )


def export_definition_payload(definition: WorkflowDefinition) -> dict:
    detail = serialize_definition_detail(Session.object_session(definition), definition)  # type: ignore[arg-type]
    return detail.model_dump(mode="json")


def to_yaml(value, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {json.dumps(item, ensure_ascii=False)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {json.dumps(item, ensure_ascii=False)}")
        return "\n".join(lines)
    return f"{prefix}{json.dumps(value, ensure_ascii=False)}"


@router.get("/definitions/{definition_id}/export")
def export_definition(definition_id: UUID, format: str = Query(default="json", pattern="^(json|yaml)$"), db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> Response:
    definition = get_definition(db, definition_id)
    payload = serialize_definition_detail(db, definition).model_dump(mode="json")
    if format == "yaml":
        return Response(content=to_yaml(payload), media_type="application/yaml")
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json")


@router.get("/search", response_model=WorkflowSearchResponse)
def workflow_search(q: str = Query(min_length=2, max_length=settings.max_search_length), db: Session = Depends(get_db), _: User = Depends(require_permission("workflows.view"))) -> WorkflowSearchResponse:
    pattern = f"%{q}%"
    items: list[WorkflowSearchResult] = []
    for definition in db.scalars(select(WorkflowDefinition).where(or_(WorkflowDefinition.code.ilike(pattern), WorkflowDefinition.name.ilike(pattern))).limit(10)).all():
        items.append(WorkflowSearchResult(type="процесс", label=f"{definition.code} v{definition.version}", description=definition.name, target=f"/admin/workflow-center/definitions/{definition.id}"))
    for state, definition in db.execute(select(WorkflowState, WorkflowDefinition).join(WorkflowDefinition).where(or_(WorkflowState.code.ilike(pattern), WorkflowState.name.ilike(pattern))).limit(10)).all():
        items.append(WorkflowSearchResult(type="состояние", label=state.code, description=state.name, target=f"/admin/workflow-center/definitions/{definition.id}?tab=states"))
    for transition, definition in db.execute(select(WorkflowTransition, WorkflowDefinition).join(WorkflowDefinition).where(or_(WorkflowTransition.code.ilike(pattern), WorkflowTransition.name.ilike(pattern), WorkflowTransition.permission_code.ilike(pattern))).limit(10)).all():
        items.append(WorkflowSearchResult(type="переход", label=transition.code, description=transition.name, target=f"/admin/workflow-center/definitions/{definition.id}?tab=transitions"))
    for row in db.execute(instance_query().where(or_(ContractorRequest.request_number.ilike(pattern), WorkflowDefinition.code.ilike(pattern))).limit(10)).all():
        instance = serialize_instance(row)
        items.append(WorkflowSearchResult(type="экземпляр", label=instance.business_identifier, description=instance.workflow_code, target=f"/admin/workflow-center/instances/{instance.id}"))
    return WorkflowSearchResponse(items=items)
