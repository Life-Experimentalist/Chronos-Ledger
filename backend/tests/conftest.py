# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.db import InstitutionalRole, User

# One shared in-memory database for the whole process; each test gets a
# freshly rebuilt schema via the `db` fixture below.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN_PASSWORD = "AdminPass123!"
FACULTY_PASSWORD = "FacultyPass123!"
STUDENT_PASSWORD = "StudentPass123!"

# bcrypt is deliberately slow; hash each seed password once per run.
_HASHES = {
    "admin": hash_password(ADMIN_PASSWORD),
    "faculty": hash_password(FACULTY_PASSWORD),
    "student": hash_password(STUDENT_PASSWORD),
}


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
        "faculty": User(
            id="FAC001",
            full_name="Faculty One",
            email_address="faculty@test.internal",
            credential_secure_hash=_HASHES["faculty"],
            role_type=InstitutionalRole.FACULTY,
            department_code="CSE",
        ),
        "student": User(
            id="STU001",
            full_name="Student One",
            email_address="student@test.internal",
            credential_secure_hash=_HASHES["student"],
            role_type=InstitutionalRole.STUDENT,
            department_code="CSE",
        ),
    }
    db.add_all(users.values())
    db.commit()
    return users


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # No context manager on purpose: entering it runs the lifespan, which
    # starts the APScheduler cron. Tests exercise routes, not the scheduler.
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, email, password):
    """Log in through the real endpoint and return Authorization headers."""
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
