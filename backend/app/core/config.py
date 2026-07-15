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
