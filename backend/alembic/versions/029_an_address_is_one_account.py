# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An address is one account, whatever case it is written in

users.email_address was unique exactly, so `Priya@Example.internal` and
`priya@example.internal` were two accounts, and somebody whose stored address
had a capital in it and typed it lower got a 401 that read like a wrong
password. Federated provisioning already compared without case and said in a
comment that it was alone in doing so.

The rule is now one rule: stored folded, compared folded. This index is the
half a convention cannot do. Writes fold at `User.email_address`, so what is
left to enforce is that no two rows fold to the same thing.

Nothing stored is rewritten. An address keeps the case an administrator typed,
which is what they see in the directory, and every reader folds both sides
instead of assuming. Rewriting stored case would be a separate migration and
would change what every account looks like to gain nothing.

The one operator-visible consequence: this refuses to run while two accounts
already collide under lower(), and names them and what to do about them.
Merging two accounts is a decision about people, and guessing which one to
keep is not a migration's business. Deactivating one is not the way out
either: a deactivated account keeps its address, so the collision stays. The
address on all but one of them has to change.

Revision ID: 029
Revises: 028
"""

from collections import defaultdict

import sqlalchemy as sa

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None

INDEX = "uq_users_email_address_lower"


def upgrade() -> None:
    rows = op.get_bind().execute(sa.text("SELECT id, email_address FROM users")).fetchall()
    # Grouped here rather than in SQL: string_agg and group_concat are not the
    # same function, and the accounts of one organization fit in memory many
    # times over.
    folded = defaultdict(list)
    for user_id, address in rows:
        folded[(address or "").strip().lower()].append(user_id)
    clashes = {address: ids for address, ids in folded.items() if len(ids) > 1}
    if clashes:
        named = "; ".join(
            f"{address} is {', '.join(sorted(ids))}" for address, ids in clashes.items()
        )
        raise RuntimeError(
            "these addresses belong to more than one account once case is "
            "ignored; change the address on all but one of each set with "
            f"PATCH /users/{{id}} and run this again: {named}"
        )

    op.create_index(INDEX, "users", [sa.text("lower(email_address)")], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX, table_name="users")
