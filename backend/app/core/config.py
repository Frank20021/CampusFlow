from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    Chosen: pydantic-settings over ad-hoc os.environ reads so missing/invalid
    config fails at startup instead of at first request.
    Alternative: dynaconf / YAML files. Tradeoff: extra file formats vs. the
    12-factor convention of env vars, which maps cleanly onto Docker.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CampusFlow"
    environment: str = "development"
    debug: bool = False

    database_url: str = Field(
        ...,
        description="PostgreSQL URL. postgresql:// is rewritten to the async/sync drivers.",
    )
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    cors_origins: str = "http://localhost:5173"

    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 60

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_not_placeholder(cls, value: str) -> str:
        if value.startswith("change-me"):
            raise ValueError("JWT_SECRET must be replaced with a real secret before running")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        return _rewrite_db_url(self.database_url, "postgresql+asyncpg://")

    @property
    def sync_database_url(self) -> str:
        return _rewrite_db_url(self.database_url, "postgresql+psycopg://")


def _rewrite_db_url(url: str, scheme: str) -> str:
    prefixes = (
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        "postgresql://",
        "postgres://",
    )
    for prefix in prefixes:
        if url.startswith(prefix):
            return scheme + url[len(prefix) :]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
