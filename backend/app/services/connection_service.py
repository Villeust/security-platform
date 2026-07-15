from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import (
    AuthGroupMapping,
    ConnectionConfiguration,
    ConnectionEventLog,
    ConnectionEventStatus,
    ConnectionProviderType,
    DirectoryGroup,
    Role,
)
from app.models.reference_data import Contractor, utc_now
from app.services.audit_service import write_audit
from app.services.secret_service import encrypt_json, mask_secrets

SECRET_FIELDS = {"bind_password", "client_secret", "password"}


def split_config(payload: dict) -> tuple[dict, dict]:
    secrets = {key: value for key, value in payload.items() if key in SECRET_FIELDS and value}
    config = {key: value for key, value in payload.items() if key not in SECRET_FIELDS}
    return config, secrets


def get_config(db: Session, provider_type: ConnectionProviderType) -> ConnectionConfiguration | None:
    return db.scalar(select(ConnectionConfiguration).where(ConnectionConfiguration.provider_type == provider_type))


def upsert_config(db: Session, provider_type: ConnectionProviderType, payload: dict, actor_id: UUID | None = None) -> ConnectionConfiguration:
    config_json, secrets = split_config(payload)
    item = get_config(db, provider_type)
    if item is None:
        item = ConnectionConfiguration(provider_type=provider_type, name=payload.get("name") or provider_type.value, configuration_json={}, is_active=False)
        db.add(item)
        db.flush()
    old = {"configuration_json": item.configuration_json, "encrypted_secrets": mask_secrets(item.encrypted_secrets)}
    item.name = payload.get("name") or item.name
    item.is_active = bool(payload.get("is_active", item.is_active))
    item.configuration_json = config_json
    if secrets:
        item.encrypted_secrets = encrypt_json(secrets)
    write_audit(
        db,
        "CONNECTION_CONFIG_UPDATED",
        "ConnectionConfiguration",
        item.id,
        old_data=old,
        new_data={"configuration_json": config_json, "encrypted_secrets": mask_secrets(secrets)},
        actor_id=actor_id,
    )
    log_connection_event(db, provider_type, item.id, "CONFIG_UPDATED", ConnectionEventStatus.INFO, "Configuration updated", actor_id=actor_id)
    db.commit()
    db.refresh(item)
    return item


def log_connection_event(
    db: Session,
    provider_type: ConnectionProviderType,
    configuration_id: UUID | None,
    event_type: str,
    status_value: ConnectionEventStatus,
    message: str,
    safe_details: dict | None = None,
    actor_id: UUID | None = None,
) -> ConnectionEventLog:
    log = ConnectionEventLog(provider_type=provider_type, configuration_id=configuration_id, event_type=event_type, status=status_value, message=message, safe_details=safe_details, actor_id=actor_id)
    db.add(log)
    db.flush()
    return log


def test_config(db: Session, provider_type: ConnectionProviderType, actor_id: UUID | None = None) -> dict:
    item = get_config(db, provider_type)
    if item is None or not item.is_active:
        message = f"{provider_type.value} не настроен"
        log_connection_event(db, provider_type, item.id if item else None, "CONNECTION_TEST_FAILED", ConnectionEventStatus.FAILED, message, actor_id=actor_id)
        if item:
            item.last_tested_at = utc_now()
            item.last_test_status = "not_configured"
            item.last_test_message = message
        db.commit()
        return {"status": "not_configured", "message": message}
    message = "Mock provider adapter: real network test is not configured"
    log_connection_event(db, provider_type, item.id, "CONNECTION_TEST_FAILED", ConnectionEventStatus.FAILED, message, actor_id=actor_id)
    item.last_tested_at = utc_now()
    item.last_test_status = "failed"
    item.last_test_message = message
    db.commit()
    return {"status": "failed", "message": message}


def import_directory_groups(db: Session, groups: list[dict], actor_id: UUID | None = None) -> list[DirectoryGroup]:
    imported: list[DirectoryGroup] = []
    for group in groups:
        item = db.scalar(select(DirectoryGroup).where(DirectoryGroup.provider_type == group["provider_type"], DirectoryGroup.external_id == group["external_id"]))
        if item is None:
            item = DirectoryGroup(provider_type=group["provider_type"], external_id=group["external_id"], distinguished_name=group["distinguished_name"], name=group["name"])
            db.add(item)
        item.distinguished_name = group["distinguished_name"]
        item.name = group["name"]
        item.description = group.get("description")
        item.member_count = group.get("member_count")
        item.is_active = True
        db.flush()
        log_connection_event(db, item.provider_type, item.source_configuration_id, "GROUP_IMPORTED", ConnectionEventStatus.SUCCESS, f"Imported group {item.name}", actor_id=actor_id)
        imported.append(item)
    db.commit()
    return imported


def create_mapping(db: Session, payload: dict, actor_id: UUID | None = None) -> AuthGroupMapping:
    role = db.get(Role, payload["role_id"])
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.code == "PLATFORM_ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PLATFORM_ADMIN mapping is protected")
    if role.code == "CONTRACTOR_USER" and payload.get("contractor_id") is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CONTRACTOR_USER mapping requires contractor_id")
    if payload.get("contractor_id") and db.get(Contractor, payload["contractor_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
    item = AuthGroupMapping(
        directory_group_id=payload["directory_group_id"],
        role_id=payload["role_id"],
        contractor_id=payload.get("contractor_id"),
        all_cities=payload.get("all_cities", True),
        priority=payload.get("priority", 100),
        is_active=payload.get("is_active", True),
    )
    db.add(item)
    db.flush()
    write_audit(db, "AUTH_GROUP_MAPPING_CREATED", "AuthGroupMapping", item.id, new_data={k: str(v) for k, v in payload.items() if k != "city_ids"}, actor_id=actor_id)
    db.commit()
    db.refresh(item)
    return item
