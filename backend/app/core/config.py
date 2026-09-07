# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # Organization
    org_domain_mask: str = "org.internal"
    org_profile: Literal["generic", "campus", "hospital"] = "generic"

    # VAPID (Web Push)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_contact_email: str = "admin@org.internal"

    # Telemetry, opt-in. Off by default so a self-hosted instance never
    # reaches a service the operator does not run. Set both to enable.
    telemetry_enabled: bool = False
    telemetry_endpoint: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
