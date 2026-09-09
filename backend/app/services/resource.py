# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Turning a room name into the row that stands for that room."""

from sqlalchemy.orm import Session

from app.models.db import Resource, ResourceType


def get_or_create_room(code: str, db: Session) -> Resource:
    """Return the resource a room name refers to, creating it on first sight.

    Every path that writes a room writes it through here, so a slot created
    by the importer, by POST /slots or by the demo seed all end up pointing
    at the same row rather than at three spellings of one room. Creating on
    a miss is what makes that true without an admin having to register a
    room before the first timetable can be uploaded.

    Only the code is set. Capacity, coordinates and unit are things a person
    knows and a CSV does not, so they stay null until somebody fills them in.
    """
    code = code.strip()
    existing = db.query(Resource).filter(Resource.code == code).first()
    if existing:
        return existing
    room = Resource(code=code, label=code, resource_type=ResourceType.ROOM)
    db.add(room)
    db.flush()
    return room
