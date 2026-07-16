from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.admin import ConnectionEventStatus, ConnectionProviderType


class ConnectionConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_type: ConnectionProviderType
    name: str
    is_active: bool
    configuration_json: dict
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_message: str | None


class LDAPConfigurationPayload(BaseModel):
    name: str = "LDAP"
    host: str | None = None
    port: int | None = None
    use_ssl: bool = True
    use_starttls: bool = False
    base_dn: str | None = None
    domain_suffix: str | None = None
    bind_username: str | None = None
    bind_password: str | None = None
    user_search_base: str | None = None
    group_search_base: str | None = None
    user_filter: str = "(sAMAccountName={username})"
    group_filter: str = "(objectClass=group)"
    connect_timeout: int = 5
    verify_tls: bool = True
    ca_certificate: str | None = None
    is_active: bool = False


class ADFSConfigurationPayload(BaseModel):
    name: str = "ADFS"
    authority_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str | None = None
    post_logout_redirect_uri: str | None = None
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    claim_username: str = "preferred_username"
    claim_email: str = "email"
    claim_display_name: str = "name"
    claim_groups: str = "groups"
    verify_tls: bool = True
    is_active: bool = False


class SMTPConfigurationPayload(BaseModel):
    name: str = "SMTP"
    host: str | None = None
    port: int = 587
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str = "Security Platform"
    reply_to: str | None = None
    authentication_enabled: bool = True
    use_starttls: bool = True
    use_ssl: bool = False
    verify_tls: bool = True
    timeout_seconds: int = 10
    is_active: bool = False

    @model_validator(mode="after")
    def validate_tls(self) -> "SMTPConfigurationPayload":
        if self.use_starttls and self.use_ssl:
            raise ValueError("STARTTLS and SSL cannot both be enabled")
        return self


class ConnectionTestResponse(BaseModel):
    status: str
    message: str
    safe_details: dict | None = None


class DirectoryGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_type: ConnectionProviderType
    external_id: str
    distinguished_name: str
    name: str
    description: str | None
    source_configuration_id: UUID | None
    member_count: int | None
    imported_at: datetime
    last_synced_at: datetime | None
    is_active: bool


class DirectoryGroupImportItem(BaseModel):
    provider_type: ConnectionProviderType = ConnectionProviderType.LDAP
    external_id: str
    distinguished_name: str
    name: str
    description: str | None = None
    member_count: int | None = None


class DirectoryGroupImportRequest(BaseModel):
    groups: list[DirectoryGroupImportItem]


class AuthGroupMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    directory_group_id: UUID
    role_id: UUID
    contractor_id: UUID | None
    all_cities: bool
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthGroupMappingPayload(BaseModel):
    directory_group_id: UUID
    role_id: UUID
    contractor_id: UUID | None = None
    all_cities: bool = True
    city_ids: list[UUID] = Field(default_factory=list)
    priority: int = 100
    is_active: bool = True


class ConnectionEventLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_type: ConnectionProviderType
    configuration_id: UUID | None
    event_type: str
    status: ConnectionEventStatus
    message: str
    safe_details: dict | None
    actor_id: UUID | None
    created_at: datetime
