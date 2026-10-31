from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # The API connects as a restricted role that is subject to Row-Level Security.
    database_url: str = "postgresql+asyncpg://pf_app:pf_app@localhost:5432/personaforge"
    # Migrations run as the schema owner.
    migration_database_url: str = (
        "postgresql+asyncpg://pf_owner:pf_owner@localhost:5432/personaforge"
    )
    app_db_role: str = "pf_app"

    redis_url: str | None = None

    jwt_secret: str = Field(default="dev-only-change-me-dev-only-change-me", min_length=32)
    # Fernet key used to encrypt TOTP secrets at rest. Derived from jwt_secret when empty.
    data_encryption_key: str = ""
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 7 * 24 * 3600
    mfa_token_ttl_seconds: int = 5 * 60
    invitation_ttl_seconds: int = 7 * 24 * 3600
    otp_ttl_seconds: int = 10 * 60
    otp_max_attempts: int = 5
    cookie_secure: bool = False

    web_origin: str = "http://localhost:5173"

    email_backend: Literal["smtp", "console", "memory"] = "console"
    email_from: str = "Persona Forge <no-reply@personaforge.local>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
