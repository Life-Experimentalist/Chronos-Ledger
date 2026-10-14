# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Whole-organization operations. Today, the export (docs/portability.md)."""

import os
import tempfile

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.core import audit
from app.core.database import get_db
from app.core.security import require_roles
from app.services.portability import export_archive

router = APIRouter()

EXPORT_FILENAME = "chronos-ledger-export.zip"


@router.get(
    "/export",
    operation_id="admin.export",
    response_class=FileResponse,
    responses={200: {"content": {"application/zip": {}}}},
)
def export(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("ORG_ADMIN")),
):
    """The caller's organization's data as one zip archive, without secrets.

    An archive with secrets comes only from `chronos-engine export
    --include-secrets`, which needs the database itself. Over HTTP an admin key
    or a stolen session would otherwise be enough to take every password hash.

    Written to a temporary file first, because the zip format needs to seek
    back over what it wrote, and the file is removed once it has been sent.
    Every export is recorded in the audit log, although it is a read: it hands
    out the whole organization.
    """
    organization_id = current_user.organization_id
    # Signing in read from this session. Ending that transaction means the
    # export's own starts clean, which on PostgreSQL is what lets it begin as
    # a snapshot (export_archive).
    db.rollback()
    handle, path = tempfile.mkstemp(suffix=".zip")
    try:
        with os.fdopen(handle, "w+b") as target:
            export_archive(
                db.connection(), target, include_secrets=False, organization_id=organization_id
            )
    except BaseException:
        os.unlink(path)
        audit.record(request, 500)
        raise
    finally:
        db.rollback()
    audit.record(request, 200)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=EXPORT_FILENAME,
        background=BackgroundTask(os.unlink, path),
    )
