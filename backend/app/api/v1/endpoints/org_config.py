# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.vocabulary import labels_for

router = APIRouter()


@router.get("")
def read_org_config():
    """Public deployment profile: which vocabulary the UI should render.

    Unauthenticated on purpose; the login page already needs it.
    """
    settings = get_settings()
    return {
        "org_profile": settings.org_profile,
        "labels": labels_for(settings.org_profile),
    }
