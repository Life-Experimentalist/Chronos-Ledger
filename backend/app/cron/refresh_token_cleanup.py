# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Deletes refresh tokens a day after they expire.

Nothing else deletes a row that is left alone. A used token is kept so that
reuse can be recognized (endpoints/auth.py::refresh), and the last token of a
session nobody signed out of waits for somebody to present it, which for an
abandoned browser is never. Past expiry either one can only produce a 401, so
without this the table grows by every refresh anyone has ever made.

The day of slack keeps this from deleting a row out from under a refresh
request that is looking at it at the moment it lapses.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.db import RefreshToken

SLACK = timedelta(days=1)


def purge_expired_refresh_tokens(db: Session) -> int:
    """Delete every refresh token that expired more than SLACK ago; return the count."""
    cutoff = datetime.now(UTC) - SLACK
    purged = (
        db.query(RefreshToken)
        .filter(RefreshToken.expires_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return purged
