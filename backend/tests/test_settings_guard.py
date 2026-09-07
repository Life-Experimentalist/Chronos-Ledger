# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Production refuses to boot on the secrets that ship in this repository."""

import pytest

from app.core.config import (
    MINIMUM_SIGNING_KEY_LENGTH,
    PUBLISHED_DATABASE_URL,
    PUBLISHED_SIGNING_KEYS,
    Settings,
    assert_production_secrets_are_set,
)

GOOD_KEY = "b7f1" * 16  # 64 hex characters, the shape openssl rand -hex 32 gives
GOOD_DB = "postgresql://someone:a-real-password@db:5432/chronos_ledger"


def _settings(**overrides) -> Settings:
    """Build Settings from explicit values only.

    Init kwargs outrank the environment and any .env file in pydantic-settings,
    so these tests do not depend on the machine they run on.
    """
    base = {
        "app_env": "production",
        "jwt_secret_signing_key": GOOD_KEY,
        "database_url": GOOD_DB,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.mark.parametrize("published", sorted(PUBLISHED_SIGNING_KEYS))
def test_production_refuses_a_published_signing_key(published):
    with pytest.raises(RuntimeError) as exc:
        assert_production_secrets_are_set(_settings(jwt_secret_signing_key=published))
    assert "forge a token" in str(exc.value)


def test_production_refuses_a_short_signing_key():
    short = "a" * (MINIMUM_SIGNING_KEY_LENGTH - 1)
    with pytest.raises(RuntimeError) as exc:
        assert_production_secrets_are_set(_settings(jwt_secret_signing_key=short))
    assert str(MINIMUM_SIGNING_KEY_LENGTH) in str(exc.value)


def test_production_refuses_the_published_database_password():
    with pytest.raises(RuntimeError) as exc:
        assert_production_secrets_are_set(_settings(database_url=PUBLISHED_DATABASE_URL))
    assert "DATABASE_URL" in str(exc.value)


def test_the_refusal_never_prints_the_secret():
    """A too-short key is still somebody's real key."""
    secret = "hunter2-but-too-short"
    with pytest.raises(RuntimeError) as exc:
        assert_production_secrets_are_set(_settings(jwt_secret_signing_key=secret))
    assert secret not in str(exc.value)


def test_the_refusal_names_every_problem_at_once():
    with pytest.raises(RuntimeError) as exc:
        assert_production_secrets_are_set(
            _settings(
                jwt_secret_signing_key="insecure_dev_key_change_in_production",
                database_url=PUBLISHED_DATABASE_URL,
            )
        )
    message = str(exc.value)
    assert "JWT_SECRET_SIGNING_KEY" in message
    assert "DATABASE_URL" in message


def test_real_production_secrets_are_accepted():
    assert_production_secrets_are_set(_settings())


def test_development_keeps_the_defaults():
    """A bare checkout and the test suite must still run."""
    assert_production_secrets_are_set(
        Settings(
            app_env="development",
            jwt_secret_signing_key="insecure_dev_key_change_in_production",
            database_url=PUBLISHED_DATABASE_URL,
        )
    )
