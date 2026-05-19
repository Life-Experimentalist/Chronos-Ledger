# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    app_cors_origins: str = "http://localhost:3000,http://localhost"

    # Database
    database_url: str = "postgresql://chronos_admin:SecureCloud2026@localhost:5432/chronos_ledger"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_signing_key: str = "insecure_dev_key_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480

    # Campus
    campus_domain_mask: str = "college.internal"

    # VAPID (Web Push)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_contact_email: str = "admin@college.internal"

    # Telemetry — pings CFlair-Counter (Life-Experimentalist/CFlair-Counter).
    # Set to false to disable all server-side telemetry pings.
    telemetry_enabled: bool = True
    telemetry_endpoint: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
