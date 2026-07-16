import json
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    project_name: str = "Contractor Requests API"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        alias="BACKEND_CORS_ORIGINS",
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/contractor_requests",
        alias="DATABASE_URL",
    )
    storage_root: str = Field(default="storage", alias="STORAGE_ROOT")
    require_work_result_for_completion: bool = Field(default=True, alias="REQUIRE_WORK_RESULT_FOR_COMPLETION")
    allow_dev_auth_headers: bool = Field(default=True, alias="ALLOW_DEV_AUTH_HEADERS")
    password_min_length: int = Field(default=12, alias="PASSWORD_MIN_LENGTH")
    password_require_uppercase: bool = Field(default=True, alias="PASSWORD_REQUIRE_UPPERCASE")
    password_require_lowercase: bool = Field(default=True, alias="PASSWORD_REQUIRE_LOWERCASE")
    password_require_digit: bool = Field(default=True, alias="PASSWORD_REQUIRE_DIGIT")
    password_require_special: bool = Field(default=True, alias="PASSWORD_REQUIRE_SPECIAL")
    password_max_length: int = Field(default=128, alias="PASSWORD_MAX_LENGTH")
    max_failed_login_attempts: int = Field(default=5, alias="MAX_FAILED_LOGIN_ATTEMPTS")
    account_lock_minutes: int = Field(default=15, alias="ACCOUNT_LOCK_MINUTES")
    password_max_age_days: int = Field(default=60, alias="PASSWORD_MAX_AGE_DAYS")
    password_expiry_warning_days: int = Field(default=7, alias="PASSWORD_EXPIRY_WARNING_DAYS")
    password_grace_logins: int = Field(default=0, alias="PASSWORD_GRACE_LOGINS")
    auth_access_cookie_name: str = Field(default="sp_access", alias="AUTH_ACCESS_COOKIE_NAME")
    auth_refresh_cookie_name: str = Field(default="sp_refresh", alias="AUTH_REFRESH_COOKIE_NAME")
    auth_csrf_cookie_name: str = Field(default="sp_csrf", alias="AUTH_CSRF_COOKIE_NAME")
    auth_access_minutes: int = Field(default=30, alias="AUTH_ACCESS_MINUTES")
    auth_refresh_days: int = Field(default=7, alias="AUTH_REFRESH_DAYS")
    auth_token_secret: str | None = Field(default=None, alias="AUTH_TOKEN_SECRET")
    auth_cookie_samesite: str = Field(default="lax", alias="AUTH_COOKIE_SAMESITE")
    auth_cookie_path: str = Field(default="/", alias="AUTH_COOKIE_PATH")
    auth_cookie_domain: str | None = Field(default=None, alias="AUTH_COOKIE_DOMAIN")
    connection_secrets_key: str | None = Field(default=None, alias="CONNECTION_SECRETS_KEY")
    admin_lock_notification_enabled: bool = Field(default=True, alias="ADMIN_LOCK_NOTIFICATION_ENABLED")
    password_expiry_notification_enabled: bool = Field(default=True, alias="PASSWORD_EXPIRY_NOTIFICATION_ENABLED")
    notification_email_enabled: bool = Field(default=False, alias="NOTIFICATION_EMAIL_ENABLED")
    service_name: str = Field(default="security-platform-api", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")
    log_health_requests: bool = Field(default=False, alias="LOG_HEALTH_REQUESTS")
    correlation_id_header: str = Field(default="X-Correlation-ID", alias="CORRELATION_ID_HEADER")
    public_base_url: str | None = Field(default=None, alias="PUBLIC_BASE_URL")
    hsts_enabled: bool = Field(default=False, alias="HSTS_ENABLED")
    max_request_body_bytes: int = Field(default=25 * 1024 * 1024, alias="MAX_REQUEST_BODY_BYTES")
    max_json_body_bytes: int = Field(default=1024 * 1024, alias="MAX_JSON_BODY_BYTES")
    max_multipart_body_bytes: int = Field(default=25 * 1024 * 1024, alias="MAX_MULTIPART_BODY_BYTES")
    max_upload_file_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_UPLOAD_FILE_BYTES")
    max_files_per_request: int = Field(default=1, alias="MAX_FILES_PER_REQUEST")
    default_page_limit: int = Field(default=100, alias="DEFAULT_PAGE_LIMIT")
    max_page_limit: int = Field(default=200, alias="MAX_PAGE_LIMIT")
    max_search_length: int = Field(default=128, alias="MAX_SEARCH_LENGTH")
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")
    auth_rate_limit_per_minute: int = Field(default=10, alias="AUTH_RATE_LIMIT_PER_MINUTE")
    debug_enabled: bool = Field(default=False, alias="APP_DEBUG")

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("auth_cookie_samesite")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax, strict or none")
        return normalized

    @field_validator("backend_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        if any(origin == "*" for origin in value):
            raise ValueError("BACKEND_CORS_ORIGINS cannot contain wildcard origins when credentials are enabled")
        for origin in value:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ValueError("BACKEND_CORS_ORIGINS must contain absolute http(s) origins without paths")
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        production = self.environment.lower() in {"production", "prod"}
        if not production:
            return self
        if not self.backend_cors_origins:
            raise ValueError("BACKEND_CORS_ORIGINS is required in production")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.backend_cors_origins):
            raise ValueError("Production CORS origins must not use localhost defaults")
        unsafe_secret_values = {"change-me", "test-secret", "secret", "dev-only-change-before-production"}
        if not self.auth_token_secret or self.auth_token_secret in unsafe_secret_values:
            raise ValueError("AUTH_TOKEN_SECRET must be set to a production secret")
        if not self.connection_secrets_key or self.connection_secrets_key in unsafe_secret_values or self.connection_secrets_key == "test-secret-key":
            raise ValueError("CONNECTION_SECRETS_KEY must be set to a production secret")
        if self.allow_dev_auth_headers:
            raise ValueError("ALLOW_DEV_AUTH_HEADERS must be false in production")
        if self.debug_enabled:
            raise ValueError("DEBUG must be false in production")
        if not self.hsts_enabled:
            raise ValueError("HSTS_ENABLED must be true in production")
        if self.auth_cookie_samesite == "none" and not self.hsts_enabled:
            raise ValueError("AUTH_COOKIE_SAMESITE=none requires HTTPS/HSTS configuration in production")
        if not self.public_base_url:
            raise ValueError("PUBLIC_BASE_URL is required in production")
        parsed = urlparse(self.public_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("PUBLIC_BASE_URL must be an HTTPS URL in production")
        return self


settings = Settings()
