# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The seeded administrator's first password comes from the environment.

Migration 001 seeds that account with a hash of a random string it throws away,
so nothing can log in as the administrator until an operator says what the
password is. These cover the one function that reads the variable, and in
particular the two things it must not do: reset a password somebody is already
using, and rewrite the column on every restart.

There is no seeded admin in this suite's database. The rest of the tests build
their schema with create_all rather than by running the migrations, so the row
001 inserts is not there and each test here makes its own.
"""

from app.core.bootstrap import SEEDED_ADMIN_ID, apply_initial_admin_password
from app.core.security import hash_password, verify_password
from app.models.db import InstitutionalRole, User

# What 001 leaves behind, and what 014 leaves behind: a hash of something
# nobody kept.
DISCARDED = "wSm2nQ7lKcYb0xTfR4pA"
CHOSEN = "TheOperatorChoseThis1!"
FROM_ENV = "WhatTheEnvironmentSays2!"


def _seeded_admin(db, password=DISCARDED, unused=True):
    admin = User(
        id=SEEDED_ADMIN_ID,
        full_name="Organization Administrator",
        email_address="admin@org.internal",
        credential_secure_hash=hash_password(password),
        role_type=InstitutionalRole.SUPER_ADMIN,
        initial_login_state=unused,
    )
    db.add(admin)
    db.commit()
    return admin


def test_the_environment_opens_an_account_nobody_has_used(db):
    admin = _seeded_admin(db)

    assert apply_initial_admin_password(db, FROM_ENV) is True
    assert verify_password(FROM_ENV, admin.credential_secure_hash)


def test_an_account_already_in_use_is_left_alone(db):
    """The whole reason this reads the flag rather than just writing.

    An operator who logged in and chose a password has initial_login_state
    false. A variable still sitting in .env after that must not be a standing
    reset that hands the account back on every restart.
    """
    admin = _seeded_admin(db, password=CHOSEN, unused=False)

    assert apply_initial_admin_password(db, FROM_ENV) is False
    assert verify_password(CHOSEN, admin.credential_secure_hash)


def test_an_empty_variable_changes_nothing(db):
    admin = _seeded_admin(db)
    before = admin.credential_secure_hash

    assert apply_initial_admin_password(db, "") is False
    assert admin.credential_secure_hash == before


def test_a_restart_does_not_rewrite_the_hash(db):
    """bcrypt salts every call, so applying twice would look like a change."""
    admin = _seeded_admin(db)
    apply_initial_admin_password(db, FROM_ENV)
    after_first = admin.credential_secure_hash

    assert apply_initial_admin_password(db, FROM_ENV) is False
    assert admin.credential_secure_hash == after_first


def test_no_seeded_admin_is_not_an_error(db):
    """Somebody deleted the account, or renamed it. Not something to recreate."""
    assert apply_initial_admin_password(db, FROM_ENV) is False


def test_a_reset_account_is_opened_again_by_the_variable(db):
    """Documenting the sharp edge rather than pretending it is not there.

    Resetting an admin's password sets initial_login_state back to true, which
    is the same state a fresh install is in, so a restart before that admin's
    next login hands the account to the variable rather than to the password
    the reset generated. The account is reachable either way, and .env.example
    says to remove the line once you are in.
    """
    admin = _seeded_admin(db, password=CHOSEN, unused=True)

    assert apply_initial_admin_password(db, FROM_ENV) is True
    assert verify_password(FROM_ENV, admin.credential_secure_hash)
