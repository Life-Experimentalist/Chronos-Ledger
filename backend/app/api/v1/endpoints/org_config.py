# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter

from app.core.config import get_settings, label_overrides
from app.core.vocabulary import labels_for

router = APIRouter()


@router.get("")
def read_org_config():
    """Public deployment profile: what the UI needs before anyone has logged in.

    Unauthenticated on purpose; the login page already needs it.

    `password_min_length` is here rather than in the auth schema because the
    onboarding wizard has to state the rule in a placeholder and refuse a short
    password in the browser, both of which happen before any request that could
    carry the number back. Publishing it tells an attacker the shortest password
    worth guessing, which they would learn from one 422 anyway.
    """
    settings = get_settings()
    return {
        "org_profile": settings.org_profile,
        "labels": labels_for(settings.org_profile, label_overrides(settings)),
        "password_min_length": settings.password_min_length,
    }
