# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.services.ingestion_engine import ChronosIngestionEngine

router = APIRouter()


@router.post("/upload-csv")
async def upload_csv(
    cycle_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN")),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    tmp_path = f"/tmp/chronos_upload_{uuid.uuid4().hex}.csv"
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        engine = ChronosIngestionEngine(db)
        result = engine.process_student_centric_matrix(tmp_path, cycle_id)

        if result["status"] == "FAILED":
            raise HTTPException(status_code=422, detail=result["error_log"])

        return result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/generate-ledger")
def trigger_ledger_generation(
    target_date: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    import datetime

    from app.cron.ledger_generator import generate_daily_ledger_entries

    if target_date:
        date_obj = datetime.date.fromisoformat(target_date)
    else:
        date_obj = datetime.date.today() + datetime.timedelta(days=1)

    generate_daily_ledger_entries(date_obj, db)
    return {"status": "generated", "date": str(date_obj)}
