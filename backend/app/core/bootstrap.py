# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""The first password for the seeded administrator account.

Migration 001 seeds one SUPER_ADMIN, because an instance with no way in is not
a deployment. It used to seed that account with a password written into the
migration file, in a public repository, which is the same as seeding no
password at all: whoever reached the instance first could read the password out
of the source and take the account before its owner arrived. It now seeds a
hash of a random string it throws away, so the account exists and nothing can
log into it, and the operator says what the first password is through
INITIAL_ADMIN_PASSWORD.

Applied on every boot, which is safe because of the one condition below: the
variable can open an account that is still waiting for a password, and cannot
reach one somebody is already using.
"""

import logging

from app.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)

# The account migration 001 seeds. Migration 004 renames its email and
# migration 014 rotates its hash, both by this id.
SEEDED_ADMIN_ID = "ADMIN001"


def apply_initial_admin_password(db, password: str) -> bool:
    """Open the seeded administrator account. True where the password changed.

    Only while initial_login_state is true. That flag is what
    core/security.py's first-login gate reads, and clearing it is the last
    thing /auth/change-password does, so it is exactly "this account has no
    password of its own yet". An operator who has logged in and chosen one
    keeps it whatever the environment says, and a variable left in place after
    that is inert rather than a standing reset.

    One caveat, because it looks like a bug from the outside: resetting an
    admin's password through the users endpoint sets that flag back to true, so
    a restart between the reset and that admin's next login hands the account
    back to this variable rather than to the password the reset generated. The
    account is reachable either way, and .env.example says to remove the line
    once you are in.

    Takes the password rather than reading the settings, so a test can call
    this without working around the lru_cache on get_settings.
    """
    from app.models.db import User

    admin = db.query(User).filter(User.id == SEEDED_ADMIN_ID).first()
    if admin is None or not admin.initial_login_state:
        return False

    if not password:
        logger.warning(
            "INITIAL_ADMIN_PASSWORD is not set, so the administrator account "
            "%s may still be holding a password nobody knows. Set the "
            "variable and restart.",
            SEEDED_ADMIN_ID,
        )
        return False

    if verify_password(password, admin.credential_secure_hash):
        # Already what the environment asks for. Hashing it again would give
        # the same password a new salt on every restart: a write, a log line
        # and a changed column that all mean nothing.
        return False

    admin.credential_secure_hash = hash_password(password)
    db.commit()
    logger.info("Applied INITIAL_ADMIN_PASSWORD to %s.", SEEDED_ADMIN_ID)
    return True
