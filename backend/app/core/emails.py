# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""One rule for an email address, used on both sides of every comparison.

An address is stored folded to lower case and compared folded to lower case.
The domain half is case-insensitive by specification and the local half is not,
but no mail system anybody runs treats `Priya@` and `priya@` as two people, and
this column is what an account signs in with. Two accounts differing only by
case were two accounts, and somebody whose stored address had a capital in it
got a 401 that read like a wrong password.

Folding is done here rather than in the schemas because three writers never see
a schema: the demo seed, the roster import and federated provisioning all build
a `User` directly. `User.email_address` runs this on assignment, and a unique
index on `lower(email_address)` means the database holds the line rather than
the convention.
"""


def normalize_email(value: str) -> str:
    return value.strip().lower()
