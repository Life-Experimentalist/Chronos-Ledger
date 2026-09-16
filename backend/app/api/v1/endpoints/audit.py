# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.pagination import Page
from app.core.security import require_roles
from app.core.time import org_timezone
from app.models.db import AuditRecord

router = APIRouter()


@router.get("/", operation_id="audit.list")
def list_audit_records(
    from_: datetime.date | None = Query(None, alias="from"),
    to: datetime.date | None = None,
    actor_id: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    """The writes made through the API, newest first.

    from and to are dates in the organization's timezone, both included, so
    a day means the day as the people working in it count it.
    """
    if from_ is not None and to is not None and to < from_:
        raise HTTPException(status_code=422, detail="to is before from")
    zone = org_timezone()
    # Bounds go in as UTC. SQLite keeps the wall time it was given and drops
    # the zone, and every record was written in UTC.
    q = db.query(AuditRecord)
    if from_ is not None:
        start = datetime.datetime.combine(from_, datetime.time.min, tzinfo=zone).astimezone(UTC)
        q = q.filter(AuditRecord.at >= start)
    if to is not None:
        next_day = to + datetime.timedelta(days=1)
        end = datetime.datetime.combine(next_day, datetime.time.min, tzinfo=zone).astimezone(UTC)
        q = q.filter(AuditRecord.at < end)
    if actor_id is not None:
        q = q.filter(AuditRecord.actor_id == actor_id)
    return [
        {
            "id": r.id,
            "at": (r.at if r.at.tzinfo else r.at.replace(tzinfo=UTC)).isoformat(),
            "actor_id": r.actor_id,
            "api_key_id": r.api_key_id,
            "method": r.method,
            "path": r.path,
            "status_code": r.status_code,
        }
        for r in page.rows(q, AuditRecord.at.desc(), AuditRecord.id.desc())
    ]
