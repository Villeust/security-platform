from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reference_data import City, ContractorResponsibility, Facility, Premise, WorkType
from app.models.requests import (
    AssignmentStatus,
    ContractorRequest,
    RequestAssignment,
    RequestAttachment,
    RequestAttachmentCategory,
    RequestHistory,
    RequestHistoryActorType,
    RequestHistoryEventType,
    RequestStatus,
    RequestWorkType,
    utc_now,
)
from app.schemas.requests import ContractorRequestCreate, ContractorRequestUpdate
from app.services.contractor_request_workflow import (
    ensure_instance_for_request,
    execute_request_status_transition,
    record_request_status_transition_after_change,
    synchronize_instance_from_request,
    workflow_actor_from_request_history,
)
from app.services.workflow_adapters import WorkflowActor


REQUEST_STATUS_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.DRAFT: {RequestStatus.NEW, RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED},
    RequestStatus.NEW: {RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED, RequestStatus.CANCELLED},
    RequestStatus.PARTIALLY_ASSIGNED: {RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.ASSIGNED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.IN_PROGRESS: {RequestStatus.COMPLETED, RequestStatus.CANCELLED},
    RequestStatus.COMPLETED: {RequestStatus.CLOSED, RequestStatus.IN_PROGRESS},
    RequestStatus.CLOSED: set(),
    RequestStatus.CANCELLED: set(),
}

ASSIGNMENT_STATUS_TRANSITIONS: dict[AssignmentStatus, set[AssignmentStatus]] = {
    AssignmentStatus.ASSIGNED: {AssignmentStatus.ACCEPTED, AssignmentStatus.CANCELLED},
    AssignmentStatus.ACCEPTED: {AssignmentStatus.IN_PROGRESS, AssignmentStatus.CANCELLED},
    AssignmentStatus.IN_PROGRESS: {AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED},
    AssignmentStatus.COMPLETED: set(),
    AssignmentStatus.CANCELLED: set(),
}

FULL_EDIT_STATUSES = {RequestStatus.DRAFT}
LIMITED_EDIT_FIELDS = {"title", "description", "contact_name", "contact_email", "contact_phone", "desired_completion_date", "priority"}
SCOPE_FIELDS = {"city_id", "facility_id", "premise_id", "work_type_ids"}


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (UUID, datetime)):
        return str(value)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def add_history(
    request: ContractorRequest,
    event_type: RequestHistoryEventType,
    actor_type: RequestHistoryActorType,
    old_status: RequestStatus | None = None,
    new_status: RequestStatus | None = None,
    changed_fields: dict | None = None,
    comment: str | None = None,
    actor_id: UUID | None = None,
) -> None:
    request.history.append(
        RequestHistory(
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            changed_fields=changed_fields,
            comment=comment,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    )


def generate_request_number(request: ContractorRequest) -> str:
    created_at = request.created_at or utc_now()
    return f"CR-{created_at:%Y%m%d}-{str(request.id)[:8].upper()}"


def ensure_request_number(request: ContractorRequest) -> None:
    if request.request_number is None:
        request.request_number = generate_request_number(request)


def validate_request_scope(
    db: Session,
    city_id: UUID,
    facility_id: UUID,
    premise_id: UUID | None,
    work_type_ids: list[UUID],
) -> tuple[Facility, Premise | None, list[WorkType]]:
    if db.get(City, city_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")

    facility = db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if facility.city_id != city_id:
        raise HTTPException(status_code=422, detail="Facility does not belong to city")

    work_types = list(db.scalars(select(WorkType).where(WorkType.id.in_(work_type_ids), WorkType.is_active.is_(True))).all())
    if len(work_types) != len(work_type_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more work types not found")

    premise = None
    requires_premise = any(work_type.requires_premise for work_type in work_types)
    if requires_premise and premise_id is None:
        raise HTTPException(status_code=422, detail="premise_id is required")
    if premise_id is not None:
        premise = db.get(Premise, premise_id)
        if premise is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Premise not found")
        if premise.facility_id != facility_id:
            raise HTTPException(status_code=422, detail="Premise does not belong to facility")

    return facility, premise, work_types


def validate_publishable_request(db: Session, request: ContractorRequest) -> tuple[Facility, Premise | None, list[WorkType]]:
    missing = []
    for field_name in ("title", "description", "city_id", "facility_id"):
        if getattr(request, field_name) in (None, ""):
            missing.append(field_name)
    work_type_ids = [item.work_type_id for item in request.work_types]
    if not work_type_ids:
        missing.append("work_type_ids")
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {', '.join(missing)}")
    assert request.city_id is not None
    assert request.facility_id is not None
    return validate_request_scope(db, request.city_id, request.facility_id, request.premise_id, work_type_ids)


def find_contractor_for_work_type(
    db: Session,
    city_id: UUID,
    facility_id: UUID,
    work_type_id: UUID,
) -> ContractorResponsibility | None:
    filters = (
        (ContractorResponsibility.facility_id == facility_id,),
        (ContractorResponsibility.city_id == city_id, ContractorResponsibility.facility_id.is_(None)),
        (ContractorResponsibility.city_id.is_(None), ContractorResponsibility.facility_id.is_(None)),
    )
    for scope_filters in filters:
        responsibility = db.scalar(
            select(ContractorResponsibility)
            .where(
                ContractorResponsibility.is_active.is_(True),
                ContractorResponsibility.work_type_id == work_type_id,
                *scope_filters,
            )
            .order_by(ContractorResponsibility.priority.asc())
            .limit(1)
        )
        if responsibility is not None:
            return responsibility
    return None


def apply_premise_contacts(request: ContractorRequest, premise: Premise | None) -> None:
    if premise is None:
        return
    request.contact_name = request.contact_name or premise.owner_name
    request.contact_email = request.contact_email or premise.owner_email
    request.contact_phone = request.contact_phone or premise.owner_phone


def set_request_work_types(request: ContractorRequest, work_type_ids: list[UUID]) -> None:
    request.work_types.clear()
    request.work_types.extend(RequestWorkType(work_type_id=work_type_id) for work_type_id in work_type_ids)


def unassigned_work_type_ids(request: ContractorRequest) -> list[UUID]:
    assigned_work_type_ids = {assignment.work_type_id for assignment in request.assignments if assignment.status != AssignmentStatus.CANCELLED}
    return [item.work_type_id for item in request.work_types if item.work_type_id not in assigned_work_type_ids]


def apply_request_status(
    request: ContractorRequest,
    new_status: RequestStatus,
    actor_type: RequestHistoryActorType,
    event_type: RequestHistoryEventType,
    comment: str | None = None,
    actor_id: UUID | None = None,
) -> None:
    old_status = request.status
    if old_status == new_status:
        return
    request.status = new_status
    now = utc_now()
    if new_status == RequestStatus.COMPLETED:
        request.completed_at = now
    if new_status == RequestStatus.CLOSED:
        request.closed_at = now
    if old_status == RequestStatus.COMPLETED and new_status == RequestStatus.IN_PROGRESS:
        request.completed_at = None
        request.closed_at = None
    add_history(
        request,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        actor_type=actor_type,
        actor_id=actor_id,
        comment=comment,
    )


def create_assignments_for_request(db: Session, request: ContractorRequest) -> list[UUID]:
    assert request.city_id is not None
    assert request.facility_id is not None
    existing_work_type_ids = {assignment.work_type_id for assignment in request.assignments}
    unassigned: list[UUID] = []
    for request_work_type in request.work_types:
        if request_work_type.work_type_id in existing_work_type_ids:
            continue
        responsibility = find_contractor_for_work_type(db, request.city_id, request.facility_id, request_work_type.work_type_id)
        if responsibility is None:
            unassigned.append(request_work_type.work_type_id)
            continue
        assignment = RequestAssignment(
            contractor_id=responsibility.contractor_id,
            work_type_id=request_work_type.work_type_id,
        )
        request.assignments.append(assignment)
        add_history(
            request,
            RequestHistoryEventType.ASSIGNMENT_CREATED,
            RequestHistoryActorType.SYSTEM,
            changed_fields={"work_type_id": {"old": None, "new": str(request_work_type.work_type_id)}},
        )
    return unassigned_work_type_ids(request)


def status_after_publish(request: ContractorRequest) -> RequestStatus:
    missing = unassigned_work_type_ids(request)
    if len(missing) == len(request.work_types):
        return RequestStatus.NEW
    if missing:
        return RequestStatus.PARTIALLY_ASSIGNED
    return RequestStatus.ASSIGNED


def create_contractor_request(
    db: Session,
    payload: ContractorRequestCreate,
    request_number: str | None = None,
    commit: bool = True,
    workflow_actor: WorkflowActor | None = None,
) -> tuple[ContractorRequest, Sequence[UUID]]:
    request = ContractorRequest(
        request_number=request_number,
        city_id=payload.city_id,
        facility_id=payload.facility_id,
        premise_id=payload.premise_id,
        title=payload.title,
        description=payload.description,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        priority=payload.priority,
        desired_completion_date=payload.desired_completion_date,
        status=RequestStatus.DRAFT,
    )
    set_request_work_types(request, payload.work_type_ids)
    db.add(request)
    db.flush()
    ensure_request_number(request)
    add_history(request, RequestHistoryEventType.CREATED, RequestHistoryActorType.INTERNAL_USER, new_status=RequestStatus.DRAFT)
    actor = workflow_actor or workflow_actor_from_request_history(RequestHistoryActorType.INTERNAL_USER)
    ensure_instance_for_request(db, request)

    unassigned: Sequence[UUID] = []
    if payload.save_as_draft:
        if not request.description:
            raise HTTPException(status_code=422, detail="description is required for draft")
    else:
        request, unassigned = publish_contractor_request(db, request, commit=False, workflow_actor=actor)

    if commit:
        db.commit()
        db.refresh(request)
    return request, unassigned


def publish_contractor_request(
    db: Session,
    request: ContractorRequest,
    commit: bool = True,
    workflow_actor: WorkflowActor | None = None,
) -> tuple[ContractorRequest, Sequence[UUID]]:
    if request.status in {RequestStatus.CLOSED, RequestStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="Final request cannot be published")
    actor = workflow_actor or workflow_actor_from_request_history(RequestHistoryActorType.INTERNAL_USER)
    ensure_instance_for_request(db, request)
    old_status = request.status
    _, premise, _ = validate_publishable_request(db, request)
    apply_premise_contacts(request, premise)
    unassigned = create_assignments_for_request(db, request)
    new_status = status_after_publish(request)

    def apply_publish_status() -> None:
        apply_request_status(
            request,
            new_status,
            actor_type=RequestHistoryActorType.INTERNAL_USER,
            event_type=RequestHistoryEventType.PUBLISHED,
        )

    execute_request_status_transition(
        db,
        request,
        old_status,
        new_status,
        actor,
        apply_publish_status,
        input_data={"action": "publish", "old_status": old_status.value, "new_status": new_status.value},
    )
    if request.status == new_status:
        add_history(request, RequestHistoryEventType.PUBLISHED, RequestHistoryActorType.INTERNAL_USER, new_status=new_status)
    synchronize_instance_from_request(db, request)
    if commit:
        db.commit()
        db.refresh(request)
    return request, unassigned


def changed_fields_for_update(request: ContractorRequest, values: dict) -> dict:
    changes: dict[str, dict[str, object]] = {}
    for field_name, new_value in values.items():
        old_value = [item.work_type_id for item in request.work_types] if field_name == "work_type_ids" else getattr(request, field_name)
        if old_value != new_value:
            changes[field_name] = {"old": _json_value(old_value), "new": _json_value(new_value)}
    return changes


def update_contractor_request(
    db: Session,
    request: ContractorRequest,
    payload: ContractorRequestUpdate,
    commit: bool = True,
) -> tuple[ContractorRequest, Sequence[UUID]]:
    if request.status in {RequestStatus.CLOSED, RequestStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="Final request cannot be edited")

    values = payload.model_dump(exclude_unset=True)
    if request.status not in FULL_EDIT_STATUSES:
        forbidden = set(values) - LIMITED_EDIT_FIELDS
        if forbidden:
            raise HTTPException(status_code=409, detail=f"Fields cannot be edited in current status: {', '.join(sorted(forbidden))}")
    if request.status in {RequestStatus.IN_PROGRESS, RequestStatus.COMPLETED} and set(values).intersection(SCOPE_FIELDS):
        raise HTTPException(status_code=409, detail="Scope fields cannot be edited after work has started")

    changes = changed_fields_for_update(request, values)
    if not changes:
        return request, unassigned_work_type_ids(request)

    for field_name, value in values.items():
        if field_name == "work_type_ids":
            set_request_work_types(request, value)
            request.assignments.clear()
            continue
        setattr(request, field_name, value)

    if request.status == RequestStatus.DRAFT and request.premise_id is not None:
        premise = db.get(Premise, request.premise_id)
        apply_premise_contacts(request, premise)

    add_history(
        request,
        RequestHistoryEventType.UPDATED,
        RequestHistoryActorType.INTERNAL_USER,
        old_status=request.status,
        new_status=request.status,
        changed_fields=changes,
    )

    if commit:
        db.commit()
        db.refresh(request)
    return request, unassigned_work_type_ids(request)


def change_request_status(
    db: Session,
    request: ContractorRequest,
    new_status: RequestStatus,
    comment: str | None = None,
    commit: bool = True,
    workflow_actor: WorkflowActor | None = None,
) -> ContractorRequest:
    if new_status not in REQUEST_STATUS_TRANSITIONS[request.status]:
        raise HTTPException(status_code=409, detail=f"Invalid status transition: {request.status} -> {new_status}")
    actor = workflow_actor or workflow_actor_from_request_history(RequestHistoryActorType.INTERNAL_USER)
    old_status = request.status
    event_type = RequestHistoryEventType.STATUS_CHANGED
    if new_status == RequestStatus.CLOSED:
        event_type = RequestHistoryEventType.CLOSED
    elif new_status == RequestStatus.CANCELLED:
        event_type = RequestHistoryEventType.CANCELLED
    elif request.status == RequestStatus.COMPLETED and new_status == RequestStatus.IN_PROGRESS:
        event_type = RequestHistoryEventType.REOPENED

    def apply_status_change() -> None:
        apply_request_status(request, new_status, RequestHistoryActorType.INTERNAL_USER, event_type, comment=comment)

    execute_request_status_transition(
        db,
        request,
        old_status,
        new_status,
        actor,
        apply_status_change,
        comment=comment,
        input_data={"action": "change_status", "old_status": old_status.value, "new_status": new_status.value},
    )
    synchronize_instance_from_request(db, request)
    if commit:
        db.commit()
        db.refresh(request)
    return request


def recalculate_request_status_from_assignments(request: ContractorRequest) -> None:
    assignments = list(request.assignments)
    if assignments and all(assignment.status == AssignmentStatus.CANCELLED for assignment in assignments):
        request.status = RequestStatus.CANCELLED
        return

    missing = unassigned_work_type_ids(request)
    active_assignments = [assignment for assignment in assignments if assignment.status != AssignmentStatus.CANCELLED]
    if active_assignments and not missing and all(assignment.status == AssignmentStatus.COMPLETED for assignment in active_assignments):
        request.status = RequestStatus.COMPLETED
        request.completed_at = request.completed_at or utc_now()
        return
    if any(assignment.status in {AssignmentStatus.ACCEPTED, AssignmentStatus.IN_PROGRESS} for assignment in active_assignments):
        request.status = RequestStatus.IN_PROGRESS
        return
    if active_assignments and not missing and all(assignment.status == AssignmentStatus.ASSIGNED for assignment in active_assignments):
        request.status = RequestStatus.ASSIGNED
        return
    if missing:
        request.status = RequestStatus.PARTIALLY_ASSIGNED


def change_assignment_status(
    db: Session,
    assignment: RequestAssignment,
    new_status: AssignmentStatus,
    actor_type: RequestHistoryActorType,
    comment: str | None = None,
    actor_id: UUID | None = None,
    commit: bool = True,
) -> RequestAssignment:
    if new_status not in ASSIGNMENT_STATUS_TRANSITIONS[assignment.status]:
        raise HTTPException(status_code=409, detail=f"Invalid assignment status transition: {assignment.status} -> {new_status}")
    if new_status == AssignmentStatus.COMPLETED and settings.require_work_result_for_completion:
        work_result_exists = db.scalar(
            select(RequestAttachment.id).where(
                RequestAttachment.assignment_id == assignment.id,
                RequestAttachment.category == RequestAttachmentCategory.WORK_RESULT,
                RequestAttachment.is_deleted.is_(False),
            )
        )
        if work_result_exists is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one active work result attachment is required before completion")

    request = assignment.request
    old_request_status = request.status
    workflow_actor = workflow_actor_from_request_history(actor_type, actor_id)
    if actor_type == RequestHistoryActorType.CONTRACTOR_USER:
        workflow_actor = WorkflowActor(
            user=workflow_actor.user,
            actor_id=actor_id,
            actor_type=workflow_actor.actor_type,
            permissions=workflow_actor.permissions,
            scope={"contractor_ids": {assignment.contractor_id}},
        )
    ensure_instance_for_request(db, request)
    old_assignment_status = assignment.status
    assignment.status = new_status
    now = utc_now()
    if new_status == AssignmentStatus.ACCEPTED and assignment.accepted_at is None:
        assignment.accepted_at = now
    if new_status == AssignmentStatus.COMPLETED:
        assignment.completed_at = now

    recalculate_request_status_from_assignments(request)
    event_type = (
        RequestHistoryEventType.ASSIGNMENT_ACCEPTED
        if new_status == AssignmentStatus.ACCEPTED
        else RequestHistoryEventType.ASSIGNMENT_STATUS_CHANGED
    )
    add_history(
        request,
        event_type,
        actor_type,
        actor_id=actor_id,
        old_status=old_request_status,
        new_status=request.status,
        changed_fields={
            "assignment_status": {"old": old_assignment_status.value, "new": new_status.value},
            "assignment_id": {"old": None, "new": str(assignment.id)},
        },
        comment=comment,
    )
    record_request_status_transition_after_change(
        db,
        request,
        old_request_status,
        workflow_actor,
        comment=comment,
        input_data={
            "action": "assignment_status",
            "assignment_id": str(assignment.id),
            "assignment_status": new_status.value,
            "old_request_status": old_request_status.value,
            "new_request_status": request.status.value,
        },
    )
    if commit:
        db.commit()
        db.refresh(assignment)
    return assignment
