"""Shared pytest fixtures. Runs only inside the Dockerized test stack
(docker-compose.test.yml) against the ephemeral db-test Postgres.

Strategy:
- session scope: drop+recreate the public schema, then `alembic upgrade head`
  once, so the schema under test is the real migration output (not create_all).
- function scope: each test runs inside a transaction that is rolled back on
  teardown, so tests are isolated and data never leaks between them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings

# Backend root (where alembic.ini lives): tests/ -> backend.
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(get_settings().database_url, future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def _migrate(engine):
    """Clean schema, then apply all migrations via the real Alembic pipeline."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
        )
    yield


@pytest.fixture(autouse=True)
def _reset_policy_cache():
    """policy_service caches rules per process; clear it between tests."""
    from app.services import policy_service

    policy_service.reset_cache()
    yield
    policy_service.reset_cache()


@pytest.fixture()
def db(engine, _migrate) -> Session:
    """A transactional session; all changes are rolled back after the test."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()
