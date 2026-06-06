"""Test harness. Uses a dedicated `comply_test` database, migrated with the real
Alembic migration (so append-only triggers exist), recreated once per session."""
import os

# Point the app at the test database BEFORE importing any app module (the engine
# is built from settings at import time).
TEST_DB = "comply_test"
ADMIN_URL = "postgresql+psycopg://comply:comply@localhost:5432/postgres"
TEST_URL = f"postgresql+psycopg://comply:comply@localhost:5432/{TEST_DB}"
os.environ["DATABASE_URL"] = TEST_URL

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.database import SessionLocal  # noqa: E402


def _recreate_test_db() -> None:
    with psycopg.connect("postgresql://comply:comply@localhost:5432/postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid();",
                (TEST_DB,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS {TEST_DB};')
            cur.execute(f'CREATE DATABASE {TEST_DB};')


@pytest.fixture(scope="session", autouse=True)
def _migrated_db():
    _recreate_test_db()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def clean_graph(db):
    """Truncate mutable graph tables before a test (controls/requirements are not
    append-only, so this is allowed)."""
    db.execute(
        __import__("sqlalchemy").text(
            "TRUNCATE control_requirements, evidence_requirements, controls, "
            "requirements, frameworks RESTART IDENTITY CASCADE;"
        )
    )
    db.commit()
    yield db
