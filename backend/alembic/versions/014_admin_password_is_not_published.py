# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The seeded admin password was printed in this repository

Migration 001 seeds one SUPER_ADMIN so that a fresh install has a way in, and
it computed that account's bcrypt hash from a literal sitting in the migration
file. The file is in a public Apache-2.0 repository, so the hash was not a
secret and neither was the password: anyone who could reach a Chronos instance
could read the password out of the source and log in as the administrator
before the operator got there.

The first-login gate in core/security.py narrows that and does not close it.
An admin whose initial_login_state is still true is refused every path except
/auth/me and /auth/change-password, so the seeded account cannot read data or
mint API keys while it still holds the seeded password. What the gate does not
decide is who changes it. On an instance reachable before its operator's first
login, the first arrival sets the new password, clears the flag, and owns a
SUPER_ADMIN account.

001 no longer seeds a password anybody can know: it hashes a random string and
throws the string away, and the operator supplies the first password through
INITIAL_ADMIN_PASSWORD, which app/core/bootstrap.py applies while the account
is still unused. That fixes databases created from here on. This migration
fixes the ones already running.

The condition is the stored hash, not the flag. An admin can reset another
admin's password through the users endpoint, and that deliberately sets
initial_login_state back to true, so a deployment whose ADMIN001 was reset last
week has the flag true and a password its operator chose. Rotating on the flag
would lock that operator out of their own instance. Rotating only where the
stored hash verifies against the published literal touches the accounts that
are actually exposed and nothing else, at the cost of one bcrypt comparison
against one row, once.

After the rotation the account holds a hash of a random string discarded here,
with initial_login_state true, which is the state a fresh install is in. So the
way back in is the same on both: set INITIAL_ADMIN_PASSWORD and restart. An
operator who had already changed the password is not touched and has nothing to
do.

There is no downgrade. Putting the published password back would reopen the
hole this closes, on a live database, because somebody asked to move one
revision down. Going down from here leaves the rotated hash where it is.
"""

import secrets

import bcrypt
from sqlalchemy import text

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

# What 001 used to seed. This is the one place that has to recognise it, and
# writing it here exposes nothing: that it was never a secret is the whole
# reason this migration exists.
PUBLISHED_ADMIN_PASSWORD = b"ChronosAdmin2026!"
SEEDED_ADMIN_ID = "ADMIN001"


def upgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        text("SELECT credential_secure_hash FROM users WHERE id = :uid"),
        {"uid": SEEDED_ADMIN_ID},
    ).first()
    if row is None or not row[0]:
        # No seeded admin, or no hash on it. Somebody has been in here, and
        # what they did is not something to guess at.
        return

    try:
        exposed = bcrypt.checkpw(PUBLISHED_ADMIN_PASSWORD, row[0].encode("utf-8"))
    except ValueError:
        # Not a bcrypt hash. Same reasoning: leave it alone.
        return
    if not exposed:
        # The operator has chosen their own password. Nothing to rotate, and
        # rotating anyway would be locking them out of their own instance.
        return

    locked = bcrypt.hashpw(secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt())
    op.execute(
        text(
            "UPDATE users SET credential_secure_hash = :hash, initial_login_state = true "
            "WHERE id = :uid"
        ).bindparams(hash=locked.decode("utf-8"), uid=SEEDED_ADMIN_ID)
    )


def downgrade() -> None:
    """Deliberately does nothing. The reason is at the top of this file."""
