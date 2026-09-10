# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def open_session():
    """A session for code that is not an ordinary request handler.

    get_db is a yield dependency, so FastAPI closes it when the handler
    returns. On a websocket that is when the browser tab closes, which would
    hold one connection out of the pool for every socket anybody has open.
    This opens one, hands it over, and closes it when the block ends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_opener():
    """open_session itself, as a dependency, so a test can substitute its own.

    Handing over the opener rather than a session is what keeps the closing in
    the handler's hands instead of FastAPI's.
    """
    return open_session
