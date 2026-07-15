import json
from typing import Any

from pydantic import Field, field_validator
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
    connection_secrets_key: str | None = Field(default=None, alias="CONNECTION_SECRETS_KEY")
    admin_lock_notification_enabled: bool = Field(default=True, alias="ADMIN_LOCK_NOTIFICATION_ENABLED")
    password_expiry_notification_enabled: bool = Field(default=True, alias="PASSWORD_EXPIRY_NOTIFICATION_ENABLED")
    notification_email_enabled: bool = Field(default=False, alias="NOTIFICATION_EMAIL_ENABLED")

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
