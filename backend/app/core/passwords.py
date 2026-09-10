# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""The one place a password is judged acceptable.

Applied through the schemas rather than the routes, so every path that takes
a password from a caller goes through it and none of them can forget. The
settings are read at call time, the way `app/core/time.py` reads the zone, so
a deployment's PASSWORD_MIN_LENGTH applies without anything caring about
import order.

Generated passwords do not come through here. `users.py::reset_user_password`
and the CSV importer both mint their own from `secrets`, which is longer and
more random than any policy would ask for.
"""

from typing import Annotated

from pydantic import AfterValidator

from app.core.config import PUBLISHED_ADMIN_PASSWORDS, get_settings


def check_password(value: str) -> str:
    """Raise ValueError with a sentence the user can act on, or return the value.

    Length is the only tunable rule. Character-class requirements are left
    out on purpose: they push people towards Passw0rd! and away from a long
    passphrase, which is the opposite of what they are for.
    """
    minimum = get_settings().password_min_length
    if len(value) < minimum:
        raise ValueError(
            f"Password must be at least {minimum} characters, this one is {len(value)}"
        )
    if value in PUBLISHED_ADMIN_PASSWORDS:
        raise ValueError("That password is published in this repository, so it protects nothing")
    return value


AcceptablePassword = Annotated[str, AfterValidator(check_password)]
