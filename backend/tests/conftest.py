# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import os
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db, get_session_opener
from app.core.security import hash_api_key, hash_password
from app.main import app
from app.models.db import ApiKey, InstitutionalRole, User

# One shared in-memory database for the whole process; each test gets a
# freshly rebuilt schema via the `db` fixture below.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


# The driver opens and closes transactions on its own schedule, and one of the
# things it does is turn the RELEASE at the end of a SAVEPOINT into a commit.
# Code that inserts a row inside begin_nested() and expects the row to vanish
# when the outer transaction rolls back gets the row anyway, so a test would
# pass here and the same code would behave differently against Postgres.
#
# Taking the driver out of the business of starting transactions and starting
# them here instead is the workaround SQLAlchemy documents for this driver.
@event.listens_for(engine, "connect")
def _driver_does_not_begin(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None


@event.listens_for(engine, "begin")
def _we_begin(conn):
    conn.exec_driver_sql("BEGIN")


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN_PASSWORD = "AdminPass123!"
STAFF_PASSWORD = "StaffPass123!"
MEMBER_PASSWORD = "MemberPass123!"
# A device credential, not a password: never hashed with bcrypt.
KIOSK_KEY = "ck_test_kiosk_credential_not_a_real_secret"

# bcrypt is deliberately slow; hash each seed password once per run.
_HASHES = {
    "admin": hash_password(ADMIN_PASSWORD),
    "staff": hash_password(STAFF_PASSWORD),
    "member": hash_password(MEMBER_PASSWORD),
}


@pytest.fixture(scope="session", autouse=True)
def _rate_limiter_off():
    """The suite signs in hundreds of times, which is what a limiter is for.

    Off by default here so the tests measure the code under test rather than
    the budget, and so a developer machine that happens to be running Redis on
    localhost does not start handing out 429s partway through a run. The tests
    that exercise the limiter switch it back on for themselves.

    os.environ rather than monkeypatch because monkeypatch is function-scoped
    and this has to stand for the session.
    """
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    get_settings.cache_clear()
    yield
    os.environ.pop("RATE_LIMIT_ENABLED", None)
    get_settings.cache_clear()


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seed_users(db):
    users = {
        "admin": User(
            id="ADM001",
            full_name="Admin One",
            email_address="admin@test.internal",
            credential_secure_hash=_HASHES["admin"],
            role_type=InstitutionalRole.SUPER_ADMIN,
            # Admins are gated server-side until the first password change,
            # so the seed admin starts past that gate.
            initial_login_state=False,
        ),
        "staff": User(
            id="FAC001",
            full_name="Staff One",
            email_address="staff@test.internal",
            credential_secure_hash=_HASHES["staff"],
            role_type=InstitutionalRole.STAFF,
            unit_code="CSE",
        ),
        "member": User(
            id="STU001",
            full_name="Member One",
            email_address="member@test.internal",
            credential_secure_hash=_HASHES["member"],
            role_type=InstitutionalRole.MEMBER,
            unit_code="CSE",
        ),
    }
    db.add_all(users.values())
    db.commit()
    return users


@pytest.fixture()
def kiosk_key(db, seed_users):
    """X-API-Key headers for a lobby kiosk device.

    The kiosk is an unattended public terminal, so its service account is
    a MEMBER: it can read the directory and file a check-in, and nothing
    a member could not already do.
    """
    db.add(
        User(
            id="KIOSK01",
            full_name="Lobby Kiosk",
            email_address="kiosk@test.internal",
            credential_secure_hash=_HASHES["member"],
            role_type=InstitutionalRole.MEMBER,
        )
    )
    db.add(
        ApiKey(
            key_hash=hash_api_key(KIOSK_KEY),
            key_prefix=KIOSK_KEY[:12],
            label="Lobby kiosk",
            user_id="KIOSK01",
        )
    )
    db.commit()
    return {"X-API-Key": KIOSK_KEY}


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    @contextmanager
    def override_open_session():
        # The websocket handler opens its own session rather than taking one
        # as a dependency, and StaticPool has exactly one connection to give.
        # Hand it the fixture's session and leave the closing to the fixture.
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_opener] = lambda: override_open_session
    # No context manager on purpose: entering it runs the lifespan, which
    # starts the APScheduler cron. Tests exercise routes, not the scheduler.
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, email, password):
    """Log in through the real endpoint and return Authorization headers."""
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
