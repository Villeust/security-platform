from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.reference_data import TimestampMixin, utc_now


class WorkflowStateType(StrEnum):
    INITIAL = "INITIAL"
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class WorkflowActorType(StrEnum):
    SYSTEM = "SYSTEM"
    INTERNAL_USER = "INTERNAL_USER"
    CONTRACTOR_USER = "CONTRACTOR_USER"


class WorkflowSlaStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    BREACHED = "BREACHED"
    CANCELLED = "CANCELLED"


class DomainEventStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class DomainEventType(StrEnum):
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_TRANSITION_EXECUTED = "WORKFLOW_TRANSITION_EXECUTED"
    WORKFLOW_STATE_CHANGED = "WORKFLOW_STATE_CHANGED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    SLA_WARNING = "SLA_WARNING"
    SLA_BREACHED = "SLA_BREACHED"


class WorkflowDefinition(TimestampMixin, Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_workflow_definition_code_version"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    states: Mapped[list["WorkflowState"]] = relationship(back_populates="workflow_definition", cascade="all, delete-orphan")
    transitions: Mapped[list["WorkflowTransition"]] = relationship(back_populates="workflow_definition", cascade="all, delete-orphan")
    sla_policies: Mapped[list["WorkflowSlaPolicy"]] = relationship(back_populates="workflow_definition", cascade="all, delete-orphan")


class WorkflowState(Base):
    __tablename__ = "workflow_states"
    __table_args__ = (UniqueConstraint("workflow_definition_id", "code", name="uq_workflow_state_definition_code"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_type: Mapped[WorkflowStateType] = mapped_column(Enum(WorkflowStateType, name="workflow_state_type"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_initial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    color_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    workflow_definition: Mapped[WorkflowDefinition] = relationship(back_populates="states")


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (UniqueConstraint("workflow_definition_id", "code", name="uq_workflow_transition_definition_code"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_state_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False, index=True)
    to_state_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False, index=True)
    permission_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requires_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_reason: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_attachment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workflow_definition: Mapped[WorkflowDefinition] = relationship(back_populates="transitions")
    from_state: Mapped[WorkflowState] = relationship(foreign_keys=[from_state_id])
    to_state: Mapped[WorkflowState] = relationship(foreign_keys=[to_state_id])


class WorkflowInstance(TimestampMixin, Base):
    __tablename__ = "workflow_instances"
    __table_args__ = (
        UniqueConstraint(
            "workflow_definition_id",
            "entity_type",
            "entity_id",
            "instance_key",
            name="uq_workflow_instance_definition_entity_key",
        ),
        Index("ix_workflow_instances_entity_lookup", "entity_type", "entity_id", "instance_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="RESTRICT"), nullable=False, index=True)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    instance_key: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    parent_instance_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True, index=True)
    current_state_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    workflow_definition: Mapped[WorkflowDefinition] = relationship()
    current_state: Mapped[WorkflowState] = relationship()
    parent_instance: Mapped["WorkflowInstance | None"] = relationship(remote_side=[id])
    executions: Mapped[list["WorkflowTransitionExecution"]] = relationship(back_populates="workflow_instance", cascade="all, delete-orphan")


class WorkflowTransitionExecution(Base):
    __tablename__ = "workflow_transition_executions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_instance_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    transition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_transitions.id", ondelete="RESTRICT"), nullable=False, index=True)
    from_state_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False)
    to_state_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_states.id", ondelete="RESTRICT"), nullable=False)
    actor_type: Mapped[WorkflowActorType] = mapped_column(Enum(WorkflowActorType, name="workflow_actor_type"), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safe_result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    workflow_instance: Mapped[WorkflowInstance] = relationship(back_populates="executions")
    transition: Mapped[WorkflowTransition] = relationship()
    from_state: Mapped[WorkflowState] = relationship(foreign_keys=[from_state_id])
    to_state: Mapped[WorkflowState] = relationship(foreign_keys=[to_state_id])


class WorkflowIdempotencyRecord(Base):
    __tablename__ = "workflow_idempotency_records"
    __table_args__ = (UniqueConstraint("key", "workflow_instance_id", "transition_id", name="uq_workflow_idempotency_key"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_instance_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    transition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_transitions.id", ondelete="RESTRICT"), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    safe_response_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowSlaPolicy(Base):
    __tablename__ = "workflow_sla_policies"
    __table_args__ = (UniqueConstraint("workflow_definition_id", "code", name="uq_workflow_sla_policy_definition_code"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    state_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_states.id", ondelete="CASCADE"), nullable=True, index=True)
    transition_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_transitions.id", ondelete="CASCADE"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_before_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_calendar_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pause_in_state_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="WARNING")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    workflow_definition: Mapped[WorkflowDefinition] = relationship(back_populates="sla_policies")


class WorkflowSlaTimer(TimestampMixin, Base):
    __tablename__ = "workflow_sla_timers"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_instance_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    sla_policy_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workflow_sla_policies.id", ondelete="RESTRICT"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    warning_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[WorkflowSlaStatus] = mapped_column(Enum(WorkflowSlaStatus, name="workflow_sla_status"), nullable=False, default=WorkflowSlaStatus.ACTIVE)


class DomainEventOutbox(Base):
    __tablename__ = "domain_event_outbox"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DomainEventStatus] = mapped_column(Enum(DomainEventStatus, name="domain_event_status"), nullable=False, default=DomainEventStatus.PENDING, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
