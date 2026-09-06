# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.db import DailyLedger, DynamicState, LogVerificationState, ReverseRsvpLog, User


def route_absence_declaration(
    submitting_user: str, absence_date: str, reasoning: str, db: Session
) -> dict:
    user = db.query(User).filter(User.id == submitting_user).first()
    if not user or not user.reporting_line_manager:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reporting hierarchy missing. Contact admin to set your manager.",
        )

    log = ReverseRsvpLog(
        submitting_user_id=submitting_user,
        # The column is a Date; SQLite's dialect rejects a bare ISO string.
        target_absence_date=datetime.date.fromisoformat(absence_date),
        context_justification=reasoning,
        approval_state=LogVerificationState.PENDING_VERIFICATION,
        authorized_by_user_id=user.reporting_line_manager,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"action": "LOGGED", "tracking_reference": log.id}


def commit_absence_override(log_id: int, execution_agent: str, target_state: str, db: Session):
    log = db.query(ReverseRsvpLog).filter(ReverseRsvpLog.id == log_id).first()
    if not log:
        return

    new_state = LogVerificationState(target_state)
    log.approval_state = new_state
    log.authorized_by_user_id = execution_agent

    if new_state == LogVerificationState.VERIFIED_APPROVED:
        db.query(DailyLedger).filter(
            DailyLedger.active_instructor_id == log.submitting_user_id,
            DailyLedger.target_date == log.target_absence_date,
        ).update({"operational_state": DynamicState.ON_LEAVE, "substitute_instructor_id": None})

    db.commit()
