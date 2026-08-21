"""Tests for the DB-backed Source Registry reliability lookup.

pulse.source_registry.get_source_reliability(db, source) is the
production reliability lookup (see routers/pulse.py) - it prefers an
active `sources` row, and falls back to the pulse.reliability dict
(unchanged) for anything not registered or explicitly deactivated.

Note: the test database is built via Base.metadata.create_all (see
tests/conftest.py), not `alembic upgrade`, so the add_sources_table
migration's seed data is never present here - every row these tests
need, they create themselves.
"""

import pytest
from tourism_pulse_api.db.models.source import Source
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.pulse.source_registry import get_source_reliability


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def make_source(db_session, **overrides) -> Source:
    defaults = {
        "name": "test_source",
        "category": "commercial",
        "reliability": "0.500",
        "is_active": True,
    }
    source = Source(**{**defaults, **overrides})
    db_session.add(source)
    db_session.commit()
    return source


def test_active_registry_row_is_used(db_session) -> None:
    # A deliberately different value than any dict entry, so a pass can
    # only mean the DB row was actually consulted.
    make_source(db_session, name="test_active_source", reliability="0.123")

    assert get_source_reliability(db_session, "test_active_source") == pytest.approx(0.123)


def test_lookup_is_case_and_whitespace_insensitive(db_session) -> None:
    make_source(db_session, name="test_case_source", reliability="0.777")

    assert get_source_reliability(db_session, "  Test_Case_Source  ") == pytest.approx(0.777)


def test_inactive_registry_row_is_not_used(db_session) -> None:
    # An inactive row (e.g. a source registered ahead of its adapter
    # landing) must not override the fallback - falls through to the
    # dict's "unknown" tier since this name has no dict entry either.
    make_source(db_session, name="test_inactive_source", reliability="0.999", is_active=False)

    assert get_source_reliability(db_session, "test_inactive_source") == pytest.approx(0.40)


def test_unregistered_source_falls_back_to_dict(db_session) -> None:
    # Not in `sources` at all, but present in pulse.reliability's dict.
    assert get_source_reliability(db_session, "hotel") == pytest.approx(0.95)


def test_unrecognized_source_falls_back_to_unknown(db_session) -> None:
    assert get_source_reliability(db_session, "totally_unrecognized_source") == pytest.approx(0.40)
