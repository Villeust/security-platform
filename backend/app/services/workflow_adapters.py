from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin import User
from app.models.workflow import WorkflowTransition


@dataclass(frozen=True)
class WorkflowActor:
    user: User
    permissions: set[str]
    actor_type: str


class WorkflowEntityAdapter(ABC):
    entity_type: str

    @abstractmethod
    def get_entity(self, db: Session, entity_id: UUID, actor: WorkflowActor) -> Any:
        raise NotImplementedError

    def validate_start(self, db: Session, entity: Any, actor: WorkflowActor) -> None:
        return None

    def validate_transition(self, db: Session, entity: Any, transition: WorkflowTransition, actor: WorkflowActor, input_data: dict | None) -> None:
        return None

    def get_actor_scope(self, db: Session, entity: Any, actor: WorkflowActor) -> dict:
        return {}

    def apply_transition(self, db: Session, entity: Any, transition: WorkflowTransition, actor: WorkflowActor, input_data: dict | None) -> dict:
        return {}

    def build_safe_context(self, entity: Any) -> dict:
        return {}

    def build_notification_context(self, entity: Any, transition: WorkflowTransition) -> dict:
        return {}

    def get_required_attachments(self, transition: WorkflowTransition) -> list[str]:
        configuration = transition.configuration_json or {}
        return list(configuration.get("required_attachment_categories") or [])

    def after_transition(self, db: Session, entity: Any, transition: WorkflowTransition, actor: WorkflowActor) -> None:
        return None


class WorkflowAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, WorkflowEntityAdapter] = {}

    def register(self, adapter: WorkflowEntityAdapter) -> None:
        self._adapters[adapter.entity_type] = adapter

    def get(self, entity_type: str) -> WorkflowEntityAdapter | None:
        return self._adapters.get(entity_type)

    def unregister(self, entity_type: str) -> None:
        self._adapters.pop(entity_type, None)

    def clear(self) -> None:
        self._adapters.clear()


workflow_adapters = WorkflowAdapterRegistry()
