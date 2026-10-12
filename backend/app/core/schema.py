# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""The database schema, built from the models.

There are no migrations. The models in app/models/db.py are the schema, on
PostgreSQL and on SQLite alike, and create_all builds whatever is missing.
That is idempotent: a table that exists is left alone, so running this on
every start costs one round of catalog lookups and nothing else.

What it does not do is change a table that already exists. Until the first
real deployment a schema change means recreating the database, and a release
does not upgrade the database the one before it made. Migrations come back as
a fresh baseline when there is a deployment worth upgrading.

`python -m app.core.schema` builds the schema and exits, for anyone who wants
it done before the server starts.
"""

import secrets
import sys

from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.database import Base

# What /health reports in place of a migration revision. A string a maintainer
# bumps when the models change, so two instances can be told apart by what
# their database looks like without either reading its catalog.
SCHEMA_VERSION = "1"


def ensure_schema(engine: Engine) -> str:
    """Build whatever the database lacks, then make sure somebody can log in.

    Returns "created" when the users table had to be made, "current" when it
    was already there. Both runs end in the same state.
    """
    import app.models.db  # noqa: F401 (registers every table with the metadata)

    had_users = inspect(engine).has_table("users")
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        _seed_administrator(connection)
    return "current" if had_users else "created"


def _seed_administrator(connection) -> None:
    """One ORG_ADMIN, so a new instance has a way in. Nothing if it is there.

    Its password is random and unknown: INITIAL_ADMIN_PASSWORD opens the
    account on the first start (app/core/bootstrap.py).
    """
    from app.core.security import hash_password
    from app.models.db import InstitutionalRole, User

    session = Session(bind=connection)
    if session.execute(select(User.id).where(User.id == SEEDED_ADMIN_ID)).first():
        return
    session.add(
        User(
            id=SEEDED_ADMIN_ID,
            full_name="Organization Administrator",
            email_address="admin@org.internal",
            credential_secure_hash=hash_password(secrets.token_urlsafe(32)),
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=True,
        )
    )
    session.flush()


def main() -> int:
    from app.core.database import engine

    print(f"Schema {SCHEMA_VERSION}: {ensure_schema(engine)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
