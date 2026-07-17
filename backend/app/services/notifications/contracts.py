from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationEventContract:
    event_type: str
    declared: bool = True
    producer_implemented: bool = False
    recipient_policy_implemented: bool = False

    @property
    def supported(self) -> bool:
        return self.producer_implemented and self.recipient_policy_implemented


DECLARED_EVENT_TYPES = [
    "REQUEST_CREATED",
    "REQUEST_PUBLISHED",
    "REQUEST_ASSIGNED",
    "ASSIGNMENT_WAITING_ACCEPTANCE",
    "ASSIGNMENT_ACCEPTED",
    "ASSIGNMENT_STARTED",
    "WORK_RESULT_REQUIRED",
    "WORK_RESULT_UPLOADED",
    "REQUEST_COMPLETED",
    "REQUEST_CLOSED",
    "REQUEST_CANCELLED",
    "REQUEST_DEADLINE_APPROACHING",
    "REQUEST_OVERDUE",
    "USER_LOCKED",
    "USER_UNLOCKED",
    "PASSWORD_EXPIRING",
    "PASSWORD_EXPIRED",
    "SESSION_REVOKED",
    "ROLE_CHANGED",
    "CONNECTION_TEST_FAILED",
    "WORKFLOW_SLA_WARNING",
    "WORKFLOW_SLA_BREACHED",
    "OUTBOX_PROCESSING_FAILED",
    "PLATFORM_HEALTH_CRITICAL",
    "EXPLICIT_TEST_EVENT",
]

EVENT_CONTRACTS = {
    event_type: NotificationEventContract(event_type=event_type)
    for event_type in DECLARED_EVENT_TYPES
}
EVENT_CONTRACTS["EXPLICIT_TEST_EVENT"] = NotificationEventContract(
    event_type="EXPLICIT_TEST_EVENT",
    producer_implemented=True,
    recipient_policy_implemented=True,
)


def get_event_contract(event_type: str) -> NotificationEventContract | None:
    return EVENT_CONTRACTS.get(event_type)
