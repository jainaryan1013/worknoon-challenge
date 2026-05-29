"""SQLAlchemy engine + session factory.

A single synchronous engine for the whole app (psycopg v3). FastAPI request
handlers and the seed/migration scripts all draw sessions from here.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,  # transparently recycle dropped connections
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closed afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
