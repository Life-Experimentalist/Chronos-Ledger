# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Deletes visitor check-ins once they are GUEST_RETENTION_DAYS old.

Every check-in at the kiosk keeps the visitor's name and phone number, and
nothing else deletes one, so without this an instance holds every visitor it
has ever had. What became of a check-in does not matter here: one nobody
acted on is as old as one that was decided.

0 keeps them forever, which is how an instance behaved before the setting
existed, so upgrading deletes nothing until somebody chooses a number.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.db import GuestGateRegistry


def purge_old_guest_check_ins(db: Session, retention_days: int) -> int:
    """Delete every check-in older than retention_days; return the count. 0 deletes nothing."""
    if not retention_days:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    purged = (
        db.query(GuestGateRegistry)
        .filter(GuestGateRegistry.timestamp_marked < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return purged
