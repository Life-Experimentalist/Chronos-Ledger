# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import require_roles
from app.core.time import org_tomorrow
from app.models.db import PlanningCycle
from app.services.ingestion_engine import ChronosIngestionEngine

router = APIRouter()

_CHUNK_BYTES = 1024 * 1024


@router.post("/upload-csv")
def upload_csv(
    cycle_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # The matrix rewrites offerings and registrations across every unit,
    # so no unit-scoped admin can upload it.
    _=Depends(require_roles("SUPER_ADMIN")),
):
    # A plain def, so the import and the password hash for every new member
    # run on a worker thread. As an async def they ran on the event loop and
    # held every other request and socket until the import was done.
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    # Looked up here rather than left to the foreign key. A bad id reaching the
    # database comes back as a driver error naming a constraint, which tells an
    # admin who mistyped a number nothing they can act on.
    if not db.query(PlanningCycle).filter(PlanningCycle.id == cycle_id).first():
        raise HTTPException(status_code=404, detail="Cycle not found")

    limit_mb = get_settings().csv_upload_max_mb
    # tempfile honours the platform temp dir; a hardcoded /tmp only exists on Linux.
    fd, tmp_path = tempfile.mkstemp(prefix="chronos_upload_", suffix=".csv")
    try:
        # Copied across a piece at a time and counted on the way. Read whole,
        # the file sat in this process's memory at whatever size it was sent.
        with os.fdopen(fd, "wb") as f:
            written = 0
            while chunk := file.file.read(_CHUNK_BYTES):
                written += len(chunk)
                if written > limit_mb * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is larger than the {limit_mb} MB upload limit",
                    )
                f.write(chunk)

        engine = ChronosIngestionEngine(db)
        result = engine.process_member_centric_matrix(tmp_path, cycle_id)

        if result["status"] == "FAILED":
            raise HTTPException(status_code=422, detail=result["error_log"])

        return result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/generate-ledger")
def trigger_ledger_generation(
    target_date: datetime.date | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    from app.cron.ledger_generator import generate_daily_ledger_entries

    # Typed as a date so FastAPI refuses anything else with a 422. Parsed by
    # hand it raised ValueError inside the handler, which left the caller a 500
    # for a typo in a query string.
    date_obj = target_date or org_tomorrow()

    generate_daily_ledger_entries(date_obj, db)
    return {"status": "generated", "date": str(date_obj)}
