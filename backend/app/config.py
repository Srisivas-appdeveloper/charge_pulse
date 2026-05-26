"""Application settings loaded from environment."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "chargepulse"
    postgres_user: str = "chargepulse"
    postgres_password: str = "change_me_in_production"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # OCPP Gateway
    ocpp_gateway_host: str = "0.0.0.0"
    ocpp_gateway_port: int = 9000
    ocpp_heartbeat_interval: int = 60
    ocpp_heartbeat_timeout: int = 300

    # ML / feature pipeline
    feature_window_minutes: int = 15
    anomaly_threshold: float = 0.5
    model_store_path: str = "./ml/model_store"

    # App
    app_env: str = "development"
    app_debug: bool = True
    cors_origins: str = "http://localhost:5173"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
