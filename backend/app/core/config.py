from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    project_name: str = "Contractor Requests API"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        alias="BACKEND_CORS_ORIGINS",
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/contractor_requests",
        alias="DATABASE_URL",
    )


settings = Settings()
