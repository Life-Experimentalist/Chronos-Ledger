# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Which migration the database is at, and whether this code can run on it.

A rollback to an older image left the database at a revision the older code
had never heard of. `alembic upgrade head` then failed with "Can't locate
revision", the container restarted, and it failed the same way on every
restart with nothing saying the image was simply older than the data. The
check below runs before the upgrade and says that in one line.

`python -m app.core.migrations` runs the check and exits non-zero on a newer
database, which is how the container start command uses it.
"""

import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

BACKEND = Path(__file__).resolve().parents[2]


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config)


def database_revision(engine: Engine) -> str | None:
    """The revision stamped in the database, or None before the first migration."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def unknown_revision_message(engine: Engine) -> str | None:
    """Why this code must not start on this database, or None when it may."""
    revision = database_revision(engine)
    known = {script.revision for script in _scripts().walk_revisions()}
    if revision is None or revision in known:
        return None
    head = _scripts().get_current_head()
    return (
        f"The database is at migration {revision}, which this version of Chronos Ledger "
        f"does not know (its newest is {head}). The database was migrated by a newer "
        "release. Run that release or a later one; this one will not start on it."
    )


def main() -> int:
    from app.core.database import engine

    message = unknown_revision_message(engine)
    if message:
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
