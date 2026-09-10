# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Whether an instance publishes its own API surface.

M-16: /docs, /redoc and /openapi.json were served unconditionally, so a
production deployment handed every route, field name and enum value to anybody
who found the host.
"""

from app.core.config import Settings, docs_are_published


def _settings(**overrides) -> Settings:
    """Build Settings from explicit values only.

    Init kwargs outrank the environment and any .env file in pydantic-settings,
    so these tests do not depend on the machine they run on.
    """
    base = {"app_env": "production"}
    base.update(overrides)
    return Settings(**base)


def test_production_publishes_nothing_by_default():
    assert not docs_are_published(_settings())


def test_development_publishes_by_default():
    """The interactive docs are how somebody learns this API. Off everywhere
    would be a worse default than off where it matters."""
    assert docs_are_published(_settings(app_env="development"))


def test_production_can_turn_them_on():
    assert docs_are_published(_settings(docs_enabled=True))


def test_development_can_turn_them_off():
    assert not docs_are_published(_settings(app_env="development", docs_enabled=False))


def test_an_empty_value_means_leave_it_to_the_environment():
    """Both compose files pass ${DOCS_ENABLED:-}, so an operator who never sets
    it hands pydantic an empty string. bool("") is a ValidationError, which
    would stop the container booting over a variable nobody touched."""
    assert _settings(docs_enabled="").docs_enabled is None
    assert not docs_are_published(_settings(docs_enabled=""))
