"""
K-Laboratory Backend Configuration.

Environment-based configuration using Pydantic Settings.
All sensitive values should be set via environment variables.
"""

from functools import lru_cache
from typing import Any

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "K-Laboratory Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    allowed_hosts: list[str] = ["*"]

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: PostgresDsn = "postgresql+asyncpg://klab:klab@localhost:5432/klab"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: RedisDsn = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    # JWT Authentication
    jwt_secret_key: str = "CHANGE-ME-JWT-SECRET"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # BlueOS Integration
    blueos_host: str = "192.168.2.2"
    blueos_port: int = 80
    blueos_mavlink_port: int = 14550
    blueos_video_port: int = 5600
    blueos_api_timeout: int = 10

    # Shop Module (Stripe)
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    shop_currency: str = "USD"

    # Forum Module
    forum_posts_per_page: int = 20
    forum_max_attachment_size_mb: int = 10

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://k-laboratory.com",
    ]

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: Any) -> Any:
        """Ensure database URL uses asyncpg driver."""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
