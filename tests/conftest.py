"""Isolates the whole test suite from the shared dev/demo database.

Every `tourism_pulse_api` module reads DATABASE_URL from the environment at
*import time* (via `Settings()` in settings.py). Historically that meant
`pytest` ran directly against whatever database `.env` pointed at - the same
one the dashboard and manual ingestion runs use - so every test run wrote
real destinations/places/signals into it.

This module derives an isolated test database URL (the same connection,
just with `_test` appended to the database name) and sets it in the
environment *before* any app module is imported, so the entire suite -
including tests that call `SessionLocal()` directly rather than going
through a FastAPI dependency - runs against that database instead.

The test database is created if missing and its schema is dropped and
recreated fresh at the start of every `pytest` session, so test runs never
accumulate stale rows and never touch the dev database.

Override the target explicitly with `TEST_DATABASE_URL` if you don't want
the "append _test" convention (e.g. a CI Postgres with a fixed test DB URL).
"""

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _REPO_ROOT / ".env"
_TEST_DB_SUFFIX = "_test"


def _dev_database_url() -> str:
    # A real environment variable (e.g. exported in CI) takes precedence
    # over .env, matching pydantic-settings' own precedence.
    from_environ = os.environ.get("DATABASE_URL")

    if from_environ:
        return from_environ

    from_dotenv = dotenv_values(_ENV_FILE).get("DATABASE_URL")

    if not from_dotenv:
        raise RuntimeError(
            "DATABASE_URL is not set (checked the environment and .env). "
            "Tests need a database to point an isolated test DB at."
        )

    return from_dotenv


def _test_database_url(dev_url: str) -> str:
    override = os.environ.get("TEST_DATABASE_URL")

    if override:
        return override

    url = make_url(dev_url)

    # str(url) masks the password as "***" - render_as_string(hide_password=False)
    # is required to get a URL that will actually authenticate.
    return url.set(database=url.database + _TEST_DB_SUFFIX).render_as_string(
        hide_password=False
    )


_DEV_URL = _dev_database_url()
_TEST_URL = _test_database_url(_DEV_URL)

# Set this at import time (conftest.py is imported before any test module),
# so every subsequent `tourism_pulse_api` import - including ones inside
# test files, not just fixtures - picks up the test database.
os.environ["DATABASE_URL"] = _TEST_URL


def _ensure_test_database_exists() -> None:
    test_db_name = make_url(_TEST_URL).database
    admin_url = make_url(_DEV_URL).set(database="postgres")

    # CREATE DATABASE cannot run inside a transaction block.
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_db_name},
            ).scalar_one_or_none()

            if exists is None:
                connection.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        engine.dispose()


def pytest_configure(config) -> None:
    _ensure_test_database_exists()

    # Import only now (after DATABASE_URL is overridden above) so the
    # engine created inside db.session binds to the test database. Importing
    # the full app also registers every model on Base.metadata, which
    # create_all below depends on.
    from tourism_pulse_api.db.base import Base
    from tourism_pulse_api.db.session import SessionLocal, engine
    from tourism_pulse_api.main import app  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    _seed_sources(SessionLocal)


def _seed_sources(session_factory) -> None:
    """Seeds the `sources` table for the test DB.

    Base.metadata.create_all builds schema only, not data - the real
    add_sources_table migration's seed rows never apply here, since
    `alembic upgrade` never runs against the test database. Every
    ingestion adapter's real source name is seeded once, at session
    start, so adapter tests can reference a real `Source` row (needed to
    satisfy the source_observations/data_quality_results FK constraints)
    without each test file racing to insert the same unique `name` and
    colliding with another file's fixture.

    Deliberately a separate, hand-maintained list rather than an import
    from the migration (which is intentionally self-contained) or from
    pulse.reliability.SOURCE_RELIABILITY (which has many entries no
    adapter test actually needs a row for) - just the source names real
    adapters write signals under.
    """
    from tourism_pulse_api.db.models.source import Source

    seed_rows = [
        {"name": "ksh", "category": "government", "reliability": "1.000"},
        {"name": "eurostat", "category": "official", "reliability": "1.000"},
        {"name": "open-meteo", "category": "official", "reliability": "0.950"},
        {"name": "osm", "category": "social", "reliability": "0.650"},
        {"name": "ticketmaster", "category": "commercial", "reliability": "0.900"},
        {"name": "youtube", "category": "social", "reliability": "0.650"},
        {"name": "gdelt", "category": "news", "reliability": "0.850"},
        {
            "name": "airbnb",
            "category": "commercial",
            "reliability": "0.900",
            "is_active": False,
        },
    ]

    session = session_factory()
    try:
        for row in seed_rows:
            session.add(Source(**row))
        session.commit()
    finally:
        session.close()
