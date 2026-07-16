from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.admin import AuthGroupMapping, ConnectionConfiguration, ConnectionEventLog, ConnectionEventStatus, ConnectionProviderType, DirectoryGroup, User
from app.schemas.connections import (
    ADFSConfigurationPayload,
    AuthGroupMappingPayload,
    AuthGroupMappingResponse,
    ConnectionConfigurationResponse,
    ConnectionEventLogResponse,
    ConnectionTestResponse,
    DirectoryGroupImportRequest,
    DirectoryGroupResponse,
    LDAPConfigurationPayload,
    SMTPConfigurationPayload,
)
from app.services.connection_service import create_mapping, import_directory_groups, test_config, upsert_config

router = APIRouter(prefix="/admin", tags=["connections"])


def provider_response(item: ConnectionConfiguration | None, provider_type: ConnectionProviderType) -> ConnectionConfigurationResponse:
    if item is None:
        return ConnectionConfigurationResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            provider_type=provider_type,
            name=provider_type.value,
            is_active=False,
            configuration_json={},
            created_at=datetime.fromtimestamp(0).astimezone(),
            updated_at=datetime.fromtimestamp(0).astimezone(),
            last_tested_at=None,
            last_test_status="not_configured",
            last_test_message="Not configured",
        )
    return ConnectionConfigurationResponse.model_validate(item)


def get_provider(db: Session, provider_type: ConnectionProviderType) -> ConnectionConfiguration | None:
    return db.scalar(select(ConnectionConfiguration).where(ConnectionConfiguration.provider_type == provider_type))


@router.get("/connections/ldap", response_model=ConnectionConfigurationResponse)
def get_ldap(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.connections.view"))) -> ConnectionConfigurationResponse:
    return provider_response(get_provider(db, ConnectionProviderType.LDAP), ConnectionProviderType.LDAP)


@router.put("/connections/ldap", response_model=ConnectionConfigurationResponse)
def put_ldap(payload: LDAPConfigurationPayload, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.connections.manage"))) -> ConnectionConfigurationResponse:
    return ConnectionConfigurationResponse.model_validate(upsert_config(db, ConnectionProviderType.LDAP, payload.model_dump(), actor.id))


@router.post("/connections/ldap/test", response_model=ConnectionTestResponse)
def test_ldap(db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.connections.test"))) -> dict:
    return test_config(db, ConnectionProviderType.LDAP, actor.id)


@router.post("/connections/ldap/search-groups", response_model=list[dict])
def ldap_search_groups(_: User = Depends(require_permission("admin.connections.test"))) -> list[dict]:
    return []


@router.post("/connections/ldap/search-users", response_model=list[dict])
def ldap_search_users(_: User = Depends(require_permission("admin.connections.test"))) -> list[dict]:
    return []


@router.get("/connections/adfs", response_model=ConnectionConfigurationResponse)
def get_adfs(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.connections.view"))) -> ConnectionConfigurationResponse:
    return provider_response(get_provider(db, ConnectionProviderType.ADFS), ConnectionProviderType.ADFS)


@router.put("/connections/adfs", response_model=ConnectionConfigurationResponse)
def put_adfs(payload: ADFSConfigurationPayload, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.connections.manage"))) -> ConnectionConfigurationResponse:
    return ConnectionConfigurationResponse.model_validate(upsert_config(db, ConnectionProviderType.ADFS, payload.model_dump(), actor.id))


@router.post("/connections/adfs/test", response_model=ConnectionTestResponse)
def test_adfs(db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.connections.test"))) -> dict:
    return test_config(db, ConnectionProviderType.ADFS, actor.id)


@router.get("/connections/smtp", response_model=ConnectionConfigurationResponse)
def get_smtp(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.connections.view"))) -> ConnectionConfigurationResponse:
    return provider_response(get_provider(db, ConnectionProviderType.SMTP), ConnectionProviderType.SMTP)


@router.put("/connections/smtp", response_model=ConnectionConfigurationResponse)
def put_smtp(payload: SMTPConfigurationPayload, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.connections.manage"))) -> ConnectionConfigurationResponse:
    return ConnectionConfigurationResponse.model_validate(upsert_config(db, ConnectionProviderType.SMTP, payload.model_dump(), actor.id))


@router.post("/connections/smtp/test", response_model=ConnectionTestResponse)
def test_smtp(db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.connections.test"))) -> dict:
    return test_config(db, ConnectionProviderType.SMTP, actor.id)


@router.get("/directory-groups", response_model=list[DirectoryGroupResponse])
def list_directory_groups(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.directory_groups.view"))) -> list[DirectoryGroup]:
    return list(db.scalars(select(DirectoryGroup).order_by(DirectoryGroup.name)).all())


@router.post("/directory-groups/import", response_model=list[DirectoryGroupResponse], status_code=status.HTTP_201_CREATED)
def import_groups(payload: DirectoryGroupImportRequest, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.directory_groups.manage"))) -> list[DirectoryGroup]:
    return import_directory_groups(db, [item.model_dump() for item in payload.groups], actor.id)


@router.post("/directory-groups/sync", response_model=list[DirectoryGroupResponse])
def sync_groups(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.directory_groups.manage"))) -> list[DirectoryGroup]:
    return list(db.scalars(select(DirectoryGroup).order_by(DirectoryGroup.name)).all())


@router.post("/directory-groups/{group_id}/deactivate", response_model=DirectoryGroupResponse)
def deactivate_group(group_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.directory_groups.manage"))) -> DirectoryGroup:
    group = db.get(DirectoryGroup, group_id)
    if group is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Group not found")
    group.is_active = False
    db.commit()
    db.refresh(group)
    return group


@router.get("/auth-mappings", response_model=list[AuthGroupMappingResponse])
def list_auth_mappings(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.auth_mappings.view"))) -> list[AuthGroupMapping]:
    return list(db.scalars(select(AuthGroupMapping).order_by(AuthGroupMapping.priority)).all())


@router.post("/auth-mappings", response_model=AuthGroupMappingResponse, status_code=status.HTTP_201_CREATED)
def create_auth_mapping(payload: AuthGroupMappingPayload, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.auth_mappings.manage"))) -> AuthGroupMapping:
    return create_mapping(db, payload.model_dump(), actor.id)


@router.get("/connection-logs", response_model=list[ConnectionEventLogResponse])
def list_connection_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.connection_logs.view")),
    provider_type: ConnectionProviderType | None = None,
    status_filter: ConnectionEventStatus | None = Query(default=None, alias="status"),
    skip: int = 0,
    limit: int = 100,
) -> list[ConnectionEventLog]:
    query = select(ConnectionEventLog)
    if provider_type:
        query = query.where(ConnectionEventLog.provider_type == provider_type)
    if status_filter:
        query = query.where(ConnectionEventLog.status == status_filter)
    return list(db.scalars(query.order_by(ConnectionEventLog.created_at.desc()).offset(skip).limit(limit)).all())
