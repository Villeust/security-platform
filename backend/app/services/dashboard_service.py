from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.admin import AdminAuditLog, AdminNotification, AdminNotificationSeverity, ConnectionConfiguration, ConnectionProviderType, User
from app.models.reference_data import Contractor, Facility, utc_now
from app.models.requests import AssignmentStatus, ContractorRequest, RequestAssignment, RequestAttachment, RequestAttachmentCategory, RequestStatus, RequestWorkType
from app.schemas.dashboard import (
    DashboardActivityItem,
    DashboardAttentionItem,
    DashboardContractorSummaryItem,
    DashboardDeadlineItem,
    DashboardMetric,
    DashboardNotificationItem,
    DashboardNotificationSummary,
    DashboardPeriod,
    DashboardRequestItem,
    DashboardResponse,
    DashboardServiceStatusItem,
    DashboardStatusDistributionItem,
)


ACTIVE_REQUEST_STATUSES = {RequestStatus.NEW, RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS}
FINAL_REQUEST_STATUSES = {RequestStatus.COMPLETED, RequestStatus.CLOSED, RequestStatus.CANCELLED}
ACTIVE_ASSIGNMENT_STATUSES = {AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED, AssignmentStatus.IN_PROGRESS}


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def resolve_period(period: str) -> DashboardPeriod:
    now = utc_now()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "30d":
        start = now - timedelta(days=30)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        period = "7d"
        start = now - timedelta(days=7)
    return DashboardPeriod(key=period, date_from=start, date_to=now)


def count_requests(db: Session, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(ContractorRequest).where(*conditions)) or 0


def request_to_item(request: ContractorRequest) -> DashboardRequestItem:
    assignment = request.assignments[0] if request.assignments else None
    contractor = assignment.contractor.name if assignment and assignment.contractor else None
    return DashboardRequestItem(
        id=request.id,
        request_number=request.request_number,
        title=request.title,
        facility=request.facility.name if request.facility else None,
        city=request.facility.city.name if request.facility and request.facility.city else None,
        work_types=[item.work_type.name for item in request.work_types if item.work_type],
        contractor=contractor,
        status=request.status.value,
        priority=request.priority,
        desired_completion_date=request.desired_completion_date,
        updated_at=request.updated_at,
    )


def request_query():
    return select(ContractorRequest).options(
        selectinload(ContractorRequest.facility).selectinload(Facility.city),
        selectinload(ContractorRequest.assignments).selectinload(RequestAssignment.contractor),
        selectinload(ContractorRequest.work_types).selectinload(RequestWorkType.work_type),
    )


def bounded_requests(db: Session, *conditions, limit: int = 8) -> list[DashboardRequestItem]:
    rows = db.scalars(request_query().where(*conditions).order_by(ContractorRequest.updated_at.desc()).limit(limit)).unique().all()
    return [request_to_item(item) for item in rows]


def build_request_groups(db: Session, now, period: DashboardPeriod, limit: int) -> dict[str, list[DashboardRequestItem]]:
    no_assignment = ~exists(select(RequestAssignment.id).where(RequestAssignment.request_id == ContractorRequest.id))
    awaiting_acceptance = exists(select(RequestAssignment.id).where(RequestAssignment.request_id == ContractorRequest.id, RequestAssignment.status == AssignmentStatus.ASSIGNED))
    return {
        "new": bounded_requests(db, ContractorRequest.status == RequestStatus.NEW, limit=limit),
        "unassigned": bounded_requests(db, no_assignment, limit=limit),
        "awaiting_acceptance": bounded_requests(db, awaiting_acceptance, limit=limit),
        "in_progress": bounded_requests(db, ContractorRequest.status == RequestStatus.IN_PROGRESS, limit=limit),
        "overdue": bounded_requests(db, ContractorRequest.desired_completion_date < now, ContractorRequest.status.not_in(FINAL_REQUEST_STATUSES), limit=limit),
        "recently_completed": bounded_requests(db, ContractorRequest.status == RequestStatus.COMPLETED, ContractorRequest.completed_at >= period.date_from, limit=limit),
    }


def build_distribution(db: Session) -> list[DashboardStatusDistributionItem]:
    rows = db.execute(select(ContractorRequest.status, func.count()).group_by(ContractorRequest.status)).all()
    counts = {status.value: count for status, count in rows}
    return [DashboardStatusDistributionItem(status=status.value, count=counts.get(status.value, 0)) for status in RequestStatus]


def build_contractor_summary(db: Session, period: DashboardPeriod, now, limit: int) -> list[DashboardContractorSummaryItem]:
    contractors = db.scalars(select(Contractor).where(Contractor.is_active.is_(True)).order_by(Contractor.name).limit(limit)).all()
    items: list[DashboardContractorSummaryItem] = []
    for contractor in contractors:
        assignments = db.scalars(select(RequestAssignment).where(RequestAssignment.contractor_id == contractor.id).options(selectinload(RequestAssignment.request))).all()
        active = [item for item in assignments if item.status in ACTIVE_ASSIGNMENT_STATUSES]
        completed = [item for item in assignments if item.status == AssignmentStatus.COMPLETED and item.completed_at and aware(item.completed_at) >= period.date_from]
        completed_hours = [
            (item.completed_at - item.assigned_at).total_seconds() / 3600
            for item in completed
            if item.completed_at is not None and item.assigned_at is not None
        ]
        overdue = [
            item for item in active
            if item.request and item.request.desired_completion_date and aware(item.request.desired_completion_date) < now
        ]
        items.append(
            DashboardContractorSummaryItem(
                contractor_id=contractor.id,
                company=contractor.name,
                active_assignments=len(active),
                in_progress=sum(1 for item in active if item.status == AssignmentStatus.IN_PROGRESS),
                awaiting_acceptance=sum(1 for item in active if item.status == AssignmentStatus.ASSIGNED),
                overdue=len(overdue),
                completed=len(completed),
                average_completion_hours=round(sum(completed_hours) / len(completed_hours), 1) if completed_hours else None,
                status="active" if active else "idle",
            )
        )
    return items


def build_deadlines(db: Session, now, limit: int) -> list[DashboardDeadlineItem]:
    rows = db.scalars(
        request_query()
        .where(ContractorRequest.desired_completion_date.is_not(None), ContractorRequest.status.not_in(FINAL_REQUEST_STATUSES))
        .order_by(ContractorRequest.desired_completion_date.asc())
        .limit(limit)
    ).unique().all()
    items: list[DashboardDeadlineItem] = []
    for request in rows:
        assert request.desired_completion_date is not None
        assignment = request.assignments[0] if request.assignments else None
        deadline = aware(request.desired_completion_date)
        severity = "critical" if deadline < now else "warning" if deadline <= now + timedelta(days=1) else "informational"
        items.append(
            DashboardDeadlineItem(
                request_id=request.id,
                request_number=request.request_number,
                title=request.title,
                facility=request.facility.name if request.facility else None,
                contractor=assignment.contractor.name if assignment and assignment.contractor else None,
                desired_completion_date=request.desired_completion_date,
                severity=severity,
            )
        )
    return items


def build_activity(db: Session, limit: int) -> list[DashboardActivityItem]:
    rows = db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)).all()
    return [
        DashboardActivityItem(
            id=item.id,
            title=item.action.replace("_", " ").title(),
            category=item.entity_type,
            actor=item.actor_type,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            created_at=item.created_at,
        )
        for item in rows
    ]


def build_notifications(db: Session, limit: int) -> DashboardNotificationSummary:
    unread_conditions = (AdminNotification.read_at.is_(None), AdminNotification.is_resolved.is_(False))
    unread_count = db.scalar(select(func.count()).select_from(AdminNotification).where(*unread_conditions)) or 0
    rows = db.scalars(
        select(AdminNotification)
        .where(*unread_conditions)
        .order_by(AdminNotification.created_at.desc())
        .limit(limit)
    ).all()
    return DashboardNotificationSummary(
        unread_count=unread_count,
        items=[
            DashboardNotificationItem(id=item.id, title=item.title, message=item.message, severity=item.severity.value, created_at=item.created_at)
            for item in rows
        ],
    )


def service_status(db: Session, can_view_admin_details: bool, now) -> list[DashboardServiceStatusItem]:
    database_status = "works"
    try:
        db.execute(select(1))
    except Exception:
        database_status = "limited"

    configs = {item.provider_type: item for item in db.scalars(select(ConnectionConfiguration)).all()}

    def provider(provider_type: ConnectionProviderType, label: str, target: str) -> DashboardServiceStatusItem:
        item = configs.get(provider_type)
        status = "configured" if item and item.is_active else "not_configured"
        if item and item.last_test_status == "failed":
            status = "limited"
        return DashboardServiceStatusItem(
            key=provider_type.value.lower(),
            label=label,
            status=status,
            description="Настроено" if status == "configured" else "Требует настройки",
            last_check=item.last_tested_at if item else None,
            target=target if can_view_admin_details else None,
        )

    return [
        DashboardServiceStatusItem(key="backend", label="Backend API", status="works", description="API отвечает", last_check=now),
        DashboardServiceStatusItem(key="database", label="Database", status=database_status, description="Проверка подключения выполнена", last_check=now),
        DashboardServiceStatusItem(key="frontend", label="Frontend", status="works", description="Интерфейс доступен", last_check=now),
        provider(ConnectionProviderType.SMTP, "Email / SMTP", "/admin/connections/smtp"),
        provider(ConnectionProviderType.LDAP, "LDAP", "/admin/connections/ldap"),
        provider(ConnectionProviderType.ADFS, "ADFS", "/admin/connections/adfs"),
        DashboardServiceStatusItem(key="storage", label="File storage", status="works", description="Файловое хранилище доступно приложению", last_check=now),
        DashboardServiceStatusItem(key="notifications", label="Notification service", status="works", description="Уведомления обрабатываются платформой", last_check=now),
        DashboardServiceStatusItem(key="contractor_portal", label="Contractor Portal", status="works", description="Портал подрядчика включён", last_check=now),
    ]


def build_dashboard(db: Session, user: User, permissions: set[str], period_key: str, recent_limit: int) -> DashboardResponse:
    now = utc_now()
    period = resolve_period(period_key)
    limit = max(1, min(recent_limit, 20))
    active_requests = count_requests(db, ContractorRequest.status.in_(ACTIVE_REQUEST_STATUSES))
    new_requests = count_requests(db, ContractorRequest.status == RequestStatus.NEW)
    in_progress_requests = count_requests(db, ContractorRequest.status == RequestStatus.IN_PROGRESS)
    overdue_requests = count_requests(db, ContractorRequest.desired_completion_date < now, ContractorRequest.status.not_in(FINAL_REQUEST_STATUSES))
    completed_period = count_requests(db, ContractorRequest.status == RequestStatus.COMPLETED, ContractorRequest.completed_at >= period.date_from)
    active_contractors = db.scalar(select(func.count()).select_from(Contractor).where(Contractor.is_active.is_(True))) or 0
    awaiting_acceptance = db.scalar(select(func.count()).select_from(RequestAssignment).where(RequestAssignment.status == AssignmentStatus.ASSIGNED)) or 0
    locked_users = db.scalar(select(func.count()).select_from(User).where(User.is_locked.is_(True))) or 0
    unassigned = count_requests(db, ~exists(select(RequestAssignment.id).where(RequestAssignment.request_id == ContractorRequest.id)))
    work_result_missing = db.scalar(
        select(func.count()).select_from(RequestAssignment).where(
            RequestAssignment.status == AssignmentStatus.IN_PROGRESS,
            ~exists(
                select(RequestAttachment.id).where(
                    RequestAttachment.assignment_id == RequestAssignment.id,
                    RequestAttachment.category == RequestAttachmentCategory.WORK_RESULT,
                    RequestAttachment.is_deleted.is_(False),
                )
            ),
        )
    ) or 0
    connection_errors = db.scalar(select(func.count()).select_from(ConnectionConfiguration).where(ConnectionConfiguration.last_test_status == "failed")) or 0
    critical_notifications = db.scalar(
        select(func.count()).select_from(AdminNotification).where(
            AdminNotification.read_at.is_(None),
            AdminNotification.is_resolved.is_(False),
            AdminNotification.severity.in_([AdminNotificationSeverity.HIGH, AdminNotificationSeverity.CRITICAL]),
        )
    ) or 0

    attention_specs = [
        ("overdue", "Просроченные заявки", overdue_requests, "Срок выполнения уже прошёл", "critical", "/applications/contractor-requests"),
        ("awaiting", "Назначения ожидают принятия", awaiting_acceptance, "Подрядчики ещё не приняли работу", "warning", "/applications/contractor-requests"),
        ("unassigned", "Заявки без назначенного подрядчика", unassigned, "Требуется назначить исполнителя", "high", "/applications/contractor-requests"),
        ("work_results", "Работы требуют результата", work_result_missing, "Нужна загрузка результата работ", "warning", "/applications/contractor-requests"),
        ("locked_users", "Заблокированные пользователи", locked_users, "Проверьте причины блокировок", "high", "/admin/users"),
        ("connections", "Ошибки подключений", connection_errors, "Есть неуспешные проверки интеграций", "critical", "/admin/connections"),
        ("notifications", "Критические уведомления", critical_notifications, "Непрочитанные high/critical события", "high", "/admin/notifications"),
    ]
    attention = [
        DashboardAttentionItem(key=key, label=label, count=count, description=description, severity=severity, target=target)
        for key, label, count, description, severity, target in attention_specs
        if count > 0
    ]

    return DashboardResponse(
        generated_at=now,
        period=period,
        attention=attention,
        metrics=[
            DashboardMetric(key="active_requests", label="Активные заявки", value=active_requests, description="NEW, ASSIGNED и IN_PROGRESS"),
            DashboardMetric(key="new_requests", label="Новые заявки", value=new_requests, description="Ожидают обработки"),
            DashboardMetric(key="in_progress_requests", label="В работе", value=in_progress_requests, description="Работы выполняются"),
            DashboardMetric(key="overdue_requests", label="Просрочено", value=overdue_requests, description="Срок выполнения прошёл"),
            DashboardMetric(key="completed_period", label="Выполнено за период", value=completed_period, description="Завершено в выбранном периоде"),
            DashboardMetric(key="active_contractors", label="Активные подрядчики", value=active_contractors, description="Активные компании"),
            DashboardMetric(key="awaiting_acceptance", label="Ожидают принятия", value=awaiting_acceptance, description="Назначения в статусе ASSIGNED"),
            DashboardMetric(key="average_completion_hours", label="Средний срок выполнения", value=0, description="Будет рассчитан при накоплении SLA данных"),
        ],
        request_status_distribution=build_distribution(db),
        request_groups=build_request_groups(db, now, period, limit),
        upcoming_deadlines=build_deadlines(db, now, limit),
        contractor_summary=build_contractor_summary(db, period, now, limit),
        recent_activity=build_activity(db, limit),
        notifications=build_notifications(db, 5),
        system_status=service_status(db, "admin.system_status.view" in permissions or "admin.connections.view" in permissions, now),
    )
