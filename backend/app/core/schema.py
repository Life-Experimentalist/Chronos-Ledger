# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""The database schema, built from the models.

There are no migrations. The models in app/models/db.py are the schema, on
PostgreSQL and on SQLite alike, and create_all builds whatever is missing.
That is idempotent: a table that exists is left alone, so running this on
every start costs one round of catalog lookups and nothing else.

What it does not do is change a table that already exists. Until the first
real deployment a schema change means recreating the database, and a release
does not upgrade the database the one before it made. Chronos 0.14 and
earlier did keep an Alembic history, and a database made by them is refused
at start (_refuse_pre_015_database) rather than left half upgraded.
Migrations come back as a fresh baseline when there is a deployment worth
upgrading.

`python -m app.core.schema` builds the schema and exits, for anyone who wants
it done before the server starts.
"""

import secrets
import sys

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.database import Base
from app.core.organization import DEFAULT_ORGANIZATION_ID

# What /health reports in place of a migration revision. A string a maintainer
# bumps when the models change, so two instances can be told apart by what
# their database looks like without either reading its catalog.
SCHEMA_VERSION = "4"

# Two replicas starting together would both find the tables missing and both
# try to make them. On PostgreSQL the first one to start holds this advisory
# lock for its transaction and the other waits, then finds everything there.
# Any fixed number does; this one is "chronos" in hex.
SCHEMA_LOCK_KEY = 0x6368726F6E6F73

# Tables only Chronos makes. An alembic_version table next to all of them is
# Chronos 0.14's; next to none of them it is a host program's own.
_CHRONOS_MARKER_TABLES = ("reservations", "daily_ledger", "structural_master_slots")


def ensure_schema(engine: Engine) -> str:
    """Build whatever the database lacks, then make sure somebody can log in.

    Returns "created" when the users table had to be made, "current" when it
    was already there. Both runs end in the same state, and so do two runs at
    once: on PostgreSQL they take turns, on SQLite the file lock already makes
    them.
    """
    import app.models.db  # noqa: F401 (registers every table with the metadata)

    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCHEMA_LOCK_KEY})
        _refuse_pre_015_database(connection)
        had_users = inspect(connection).has_table("users")
        Base.metadata.create_all(connection)
        _seed_default_organization(connection)
        _seed_administrator(connection)
    return "current" if had_users else "created"


def _refuse_pre_015_database(connection) -> None:
    """Stop on a database Chronos 0.14 or earlier made, before create_all.

    Those releases migrated with Alembic and left an alembic_version table.
    create_all would find their tables present, leave them alone and start
    cleanly on a schema this release never upgraded. The lookup is unqualified,
    so on PostgreSQL it sees only the schema the engine is confined to
    (app.core.database.use_schema) or the default one, and never a host's
    tables elsewhere. A host program may keep its own alembic_version in that
    same database, so it only counts when Chronos's own tables are beside it.
    """
    inspector = inspect(connection)
    if not inspector.has_table("alembic_version"):
        return
    if not all(inspector.has_table(name) for name in _CHRONOS_MARKER_TABLES):
        return
    raise RuntimeError(
        "This database was made by Chronos 0.14 or earlier (it has an alembic_version "
        "table beside Chronos's tables), and 0.15 does not upgrade it in place. There are "
        "no migrations before the first real deployment. Export what you need, then "
        "recreate the database and start again on an empty one."
    )


def _seed_default_organization(connection) -> None:
    """The organization a new deployment's data lives in. Nothing if it is there."""
    from app.models.db import Organization

    session = Session(bind=connection)
    found = select(Organization.id).where(Organization.id == DEFAULT_ORGANIZATION_ID)
    if session.execute(found).first():
        return
    session.add(Organization(id=DEFAULT_ORGANIZATION_ID, name="Default organization"))
    session.flush()


def _seed_administrator(connection) -> None:
    """One ORG_ADMIN, so a new instance has a way in. Nothing if it is there.

    It belongs to the default organization.

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
            organization_id=DEFAULT_ORGANIZATION_ID,
        )
    )
    session.flush()


def main() -> int:
    from app.core.database import engine

    print(f"Schema {SCHEMA_VERSION}: {ensure_schema(engine)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
