# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.pagination import Page
from app.core.security import get_current_user, require_roles
from app.models.db import ResourceClass
from app.schemas.resource_classes import (
    ResourceClassCreate,
    ResourceClassResponse,
    ResourceClassUpdate,
)
from app.services.resource_classes import is_in_use

router = APIRouter()

CODE_TAKEN = "a resource class with that code already exists"
SEEDED_STAYS = "ROOM and PERSON are built in: they cannot be deleted or deactivated"
IN_USE = "a resource or a requirement still uses that class"


def _class_or_404(db: Session, code: str) -> ResourceClass:
    found = db.query(ResourceClass).filter(ResourceClass.code == code).first()
    if found is None:
        raise ChronosError(
            status_code=404, detail="Resource class not found", code=ErrorCode.NOT_FOUND
        )
    return found


@router.get("/", operation_id="resourceClasses.list", response_model=list[ResourceClassResponse])
def list_resource_classes(
    active: bool | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """The kinds of resource this organization books, in code order.

    Readable by anyone signed in, as resources are. Every organization has
    ROOM and PERSON; an administrator adds others. The page is optional.
    """
    query = db.query(ResourceClass)
    if active is not None:
        query = query.filter(ResourceClass.active == active)
    return page.rows(query, ResourceClass.code)


@router.post(
    "/",
    operation_id="resourceClasses.create",
    response_model=ResourceClassResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource_class(
    payload: ResourceClassCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Add a kind of resource.

    code is an uppercase identifier (letters, digits and underscores, starting
    with a letter), unique in the organization and permanent. A class made here
    carries no behaviour of its own: it is a label that resources are filed
    under and that requirements can ask for. A code already taken is 409.
    """
    row = ResourceClass(**payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT, detail=CODE_TAKEN, code=ErrorCode.ALREADY_EXISTS
        ) from None
    db.refresh(row)
    return row


@router.patch(
    "/{code}",
    operation_id="resourceClasses.update",
    response_model=ResourceClassResponse,
)
def update_resource_class(
    code: str,
    payload: ResourceClassUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Rename a class, or switch it off and on.

    The code cannot change. Deactivating a class stops new resources and new
    requirements naming it and leaves the ones that already do as they are.
    Deactivating ROOM or PERSON is 409 RESOURCE_CLASS_PROTECTED; renaming
    them is fine.
    """
    row = _class_or_404(db, code)
    fields = payload.model_dump(exclude_unset=True)
    if row.seeded and fields.get("active") is False:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=SEEDED_STAYS,
            code=ErrorCode.RESOURCE_CLASS_PROTECTED,
        )
    for field, value in fields.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete(
    "/{code}",
    operation_id="resourceClasses.delete",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resource_class(
    code: str,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Remove a class nothing uses.

    409 RESOURCE_CLASS_PROTECTED for ROOM and PERSON. 409
    RESOURCE_CLASS_IN_USE while any resource has the class or any requirement
    asks for it, whether the class is active or not; deactivate it instead to
    stop new uses and keep the old.
    """
    row = _class_or_404(db, code)
    if row.seeded:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=SEEDED_STAYS,
            code=ErrorCode.RESOURCE_CLASS_PROTECTED,
        )
    if is_in_use(db, code):
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=IN_USE,
            code=ErrorCode.RESOURCE_CLASS_IN_USE,
        )
    db.delete(row)
    try:
        db.commit()
    except IntegrityError:
        # A resource took the class between the check and the delete; the
        # foreign key held it.
        db.rollback()
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=IN_USE,
            code=ErrorCode.RESOURCE_CLASS_IN_USE,
        ) from None
