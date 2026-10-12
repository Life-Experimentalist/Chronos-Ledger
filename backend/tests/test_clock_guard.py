# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Nothing in app/ reads the wall clock except app/core/clock.py.

A direct read anywhere else is a timestamp a host clock cannot move, and
one row that disagrees with every other row is enough to break the
determinism docs/clock.md promises. The real-time reads that are allowed
go through clock.wall_now(), and the list of callers is the list below:
adding one means adding a reason to docs/clock.md as well.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
CLOCK = APP / "core" / "clock.py"

WALL_CLOCK = re.compile(r"datetime\.now\(|datetime\.utcnow\(|func\.now\(|time\.time\(")

# The instants an outside verifier compares against its own clock. PyJWT
# checks exp, nbf and iat against real time with no way to hand it another
# clock, so what it will check is stamped and compared on real time.
WALL_NOW_CALLERS = {
    "core/security.py",
    "api/v1/endpoints/federation.py",
    "services/federated_identity.py",
}


def _sources():
    return sorted(path for path in APP.rglob("*.py") if path != CLOCK)


def test_no_module_but_the_clock_reads_the_wall_clock():
    offenders = []
    for path in _sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if WALL_CLOCK.search(line):
                offenders.append(f"{path.relative_to(APP)}:{number}: {line.strip()}")
    assert offenders == [], "\n".join(offenders)


def test_real_time_is_read_only_where_a_verifier_forces_it():
    callers = {
        path.relative_to(APP).as_posix()
        for path in _sources()
        if "wall_now(" in path.read_text(encoding="utf-8")
    }
    assert callers == WALL_NOW_CALLERS


def test_the_database_never_stamps_its_own_time():
    from sqlalchemy import Date, DateTime, Time

    from app.core.database import Base

    stamped = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if (column.server_default is not None or column.server_onupdate is not None)
        and isinstance(column.type, (DateTime, Date, Time))
    ]
    assert stamped == []
