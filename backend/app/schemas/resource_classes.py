# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.db import RESOURCE_CLASS_CODE_LIMIT

# An uppercase identifier: a letter, then letters, digits and underscores.
CLASS_CODE_PATTERN = r"^[A-Z][A-Z0-9_]*$"
ClassCode = Annotated[
    str, Field(min_length=1, max_length=RESOURCE_CLASS_CODE_LIMIT, pattern=CLASS_CODE_PATTERN)
]


class ResourceClassResponse(BaseModel):
    id: int
    code: str
    name: str
    active: bool
    # ROOM and PERSON. They cannot be deleted or deactivated, and their code
    # cannot change.
    seeded: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ResourceClassCreate(BaseModel):
    """A new kind of resource. code is permanent, so it is chosen with care."""

    model_config = {"str_strip_whitespace": True}

    code: ClassCode
    name: str = Field(min_length=1, max_length=120)


class ResourceClassUpdate(BaseModel):
    """What may change on a class. code is absent because it is the identifier.

    Deactivating a class stops new resources and requirements naming it and
    leaves those that already do alone. A seeded class stays active.
    """

    model_config = {"str_strip_whitespace": True}

    name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None

    @model_validator(mode="after")
    def _nothing_is_cleared(self):
        # Leaving a field out keeps it; null is not a name and not a state.
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be cleared, only changed")
        return self
