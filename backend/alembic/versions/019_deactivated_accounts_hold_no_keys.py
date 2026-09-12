# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A deactivated account holds no API keys

Deactivating an account used to hold its API keys: they stopped working
while it was deactivated and worked again once it was reactivated. The
route now deletes them, because a key kept on an account nobody answers for
is a working credential nobody is accountable for, and an integration whose
account comes back is issued a new key.

That covers accounts deactivated from here on. This deletes the keys still
held by the ones deactivated before, which would otherwise come back with
the account on reactivation.

There is no downgrade. The deleted rows cannot be recovered, and a key that
comes back with its account is what this removes.
"""

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM api_keys WHERE user_id IN "
        "(SELECT id FROM users WHERE deactivated_at IS NOT NULL)"
    )


def downgrade() -> None:
    """Deliberately does nothing. The reason is at the top of this file."""
