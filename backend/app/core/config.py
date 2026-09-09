# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that are published in this repository. A deployment running on any of
# them has no secret at all, so production refuses to start rather than serving
# forgeable tokens quietly.
PUBLISHED_SIGNING_KEYS = frozenset(
    {
        # The field default below.
        "insecure_dev_key_change_in_production",
        # The placeholder in .env.example. Copying that file without editing it
        # is the same exposure as never setting the variable.
        "replace_with_64_char_hex_secret_generated_by_openssl_rand_hex_32",
    }
)
PUBLISHED_DATABASE_URL = "postgresql://chronos_admin:SecureCloud2026@localhost:5432/chronos_ledger"
MINIMUM_SIGNING_KEY_LENGTH = 32


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
    # An IANA name, not an offset. "Asia/Kolkata", not "+05:30": an offset
    # cannot know when daylight saving moves, and a schedule that runs across
    # a spring forward would drift by an hour for half the year.
    org_timezone: str = "UTC"

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

    @field_validator("org_timezone")
    @classmethod
    def _zone_must_exist(cls, name: str) -> str:
        """Refuse a name no zone database knows, at startup.

        Unlike the secret checks below this one is a pydantic validator,
        because a timezone name is not a secret and echoing the bad value is
        exactly what the operator needs to see. Falling back to UTC instead
        would put the whole schedule an offset out and say nothing.

        A slim container may have no zone database at all, in which case
        every name but UTC fails here. tzdata is a dependency for that
        reason, so the failure is a typo rather than a missing package.
        """
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as bad:
            raise ValueError(
                f"ORG_TIMEZONE={name!r} is not an IANA timezone name. "
                "It wants something like 'Asia/Kolkata' or 'Europe/London', "
                "not an offset like '+05:30'."
            ) from bad
        return name


def describe_production_secret_problems(settings: Settings) -> list[str]:
    """What is wrong with these secrets, in plain sentences, or an empty list.

    Never includes a secret value. The length of a too-short key is named
    because it is what the operator needs to act on; the key itself is not.
    """
    if settings.app_env != "production":
        return []

    problems = []
    if settings.jwt_secret_signing_key in PUBLISHED_SIGNING_KEYS:
        problems.append(
            "JWT_SECRET_SIGNING_KEY is still a placeholder published in this "
            "repository, so anyone can forge a token for any user"
        )
    elif len(settings.jwt_secret_signing_key) < MINIMUM_SIGNING_KEY_LENGTH:
        problems.append(
            f"JWT_SECRET_SIGNING_KEY is {len(settings.jwt_secret_signing_key)} characters, "
            f"below the {MINIMUM_SIGNING_KEY_LENGTH} minimum"
        )
    if settings.database_url == PUBLISHED_DATABASE_URL:
        problems.append("DATABASE_URL still carries the password published in this repository")
    return problems


def assert_production_secrets_are_set(settings: Settings) -> None:
    """Fail the process rather than boot on a public secret.

    Only fires when app_env is production, which is what every deployment path
    sets: both compose files and .env.example. Development keeps the defaults
    so the test suite and a bare checkout still run.

    Deliberately not a pydantic model_validator. Pydantic decorates a
    ValidationError with `input_value=...`, which would echo the very secret
    being complained about into the logs.
    """
    problems = describe_production_secret_problems(settings)
    if not problems:
        return
    raise RuntimeError(
        "Refusing to start with APP_ENV=production:\n  - "
        + "\n  - ".join(problems)
        + "\n\nRun ./setup.sh, which generates both, or set them yourself:\n"
        "  JWT_SECRET_SIGNING_KEY=$(openssl rand -hex 32)"
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    assert_production_secrets_are_set(settings)
    return settings
