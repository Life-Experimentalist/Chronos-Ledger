# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Tells the desk when an approved visit has run past its end.

A visit approved while GUEST_VISIT_LENGTH_MINUTES is set gets an end, and
nothing happens at that moment on its own: Chronos revokes no access and turns
nobody out, because it does not hold the door. What it can do is say so, once,
to the people who could act on it, and then leave the deciding to them.

Once, not every five minutes. overstay_notified_at is the record that somebody
was told, and an extension clears it, which is what makes a second overrun
announce itself as the first did.
"""

from sqlalchemy.orm import Session

from app.core import clock
from app.core.websocket_manager import socket_broker
from app.models.db import GuestGateRegistry, LogVerificationState


async def announce_overstayed_visits(db: Session) -> int:
    """Notify about every approved visit past its end that nobody has been told about.

    Returns how many visits were announced.
    """
    now = clock.now()
    overdue = (
        db.query(GuestGateRegistry)
        .filter(
            GuestGateRegistry.handshake_status == LogVerificationState.VERIFIED_APPROVED,
            GuestGateRegistry.visit_expires_at.isnot(None),
            GuestGateRegistry.visit_expires_at <= now,
            GuestGateRegistry.overstay_notified_at.is_(None),
        )
        .all()
    )
    for entry in overdue:
        payload = {
            "transaction_reference": entry.id,
            "guest_name": entry.guest_name,
            "visit_expires_at": entry.visit_expires_at.isoformat(),
        }
        # The person the visitor came to see, and whoever let them in when that
        # was somebody else: an admin who approved a visit at the desk is the
        # one standing where the visitor will walk back past.
        recipients = [entry.target_staff_id]
        if entry.decided_by_id and entry.decided_by_id != entry.target_staff_id:
            recipients.append(entry.decided_by_id)
        for recipient in recipients:
            await socket_broker.forward_direct_message(recipient, "GUEST_VISIT_EXPIRED", payload)
        # Stamped whether or not anybody was connected to hear it. The socket
        # reaches whoever is online and drops the rest, so a desk that was
        # logged out reads GET /guest/overstays instead; saying it again in five
        # minutes would not find them either.
        entry.overstay_notified_at = now
    db.commit()
    return len(overdue)
