# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""The kinds of resource an organization books, and who may name one.

A resource and a requirement name a class by code. Every check here goes
through the organization-scoped query, never db.get, so another
organization's class is simply not found.
"""

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import ChronosError, ErrorCode
from app.models.db import Resource, ResourceClass, ResourceRequirement


def require_active_class(db: Session, code: str) -> ResourceClass:
    """The organization's active class with this code, or 422 UNKNOWN_RESOURCE_CLASS.

    Unknown, inactive and another organization's class are told apart by
    nobody: a caller learns only that the code is not one it may use.
    """
    found = (
        db.query(ResourceClass)
        .filter(ResourceClass.code == code, ResourceClass.active.is_(True))
        .first()
    )
    if found is None:
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{code} is not an active resource class of this organization",
            code=ErrorCode.UNKNOWN_RESOURCE_CLASS,
        )
    return found


def is_in_use(db: Session, code: str) -> bool:
    """Whether any resource or requirement of the organization names the class."""
    if db.query(Resource.id).filter(Resource.resource_type == code).first() is not None:
        return True
    return (
        db.query(ResourceRequirement.id).filter(ResourceRequirement.target_kind == code).first()
        is not None
    )
