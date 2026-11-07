"""End to end against the test database, with the network replaced by
fixtures: signals land per month, and no post text reaches storage."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, SignalBreakdown
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.bluesky import __main__ as bluesky_main
from tourism_pulse_api.ingestion.reddit import __main__ as reddit_main
from tourism_pulse_api.ingestion.reddit.service import monthly_aggregates as real_aggregates
from tourism_pulse_api.scheduler import jobs

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PLACE_NAME = "Social Test Crete"


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def place(db_session) -> Place:
    destination = Destination(country_code="EL", name="Social Test Greece")
    db_session.add(destination)
    db_session.commit()
    row = Place(destination_id=destination.id, name=PLACE_NAME, place_type="destination")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _signals(db_session, place_id: int, signal_type: str) -> dict[str, float]:
    rows = (
        db_session.query(Signal)
        .filter(Signal.place_id == place_id, Signal.signal_type == signal_type)
        .all()
    )
    return {f"{r.observed_at:%Y-%m}": float(r.value) for r in rows}


def test_reddit_run_stores_monthly_aggregates_only(db_session, place, monkeypatch) -> None:
    page = (FIXTURES / "reddit_listing_crete_sample.json").read_text(encoding="utf-8")
    ended = json.loads(page)
    ended["data"]["after"] = None
    monkeypatch.setattr(reddit_main, "SUBREDDITS", {PLACE_NAME: ("crete",)})
    monkeypatch.setattr(reddit_main.settings, "reddit_client_id", "id")
    monkeypatch.setattr(reddit_main.settings, "reddit_client_secret", "secret")
    monkeypatch.setattr(reddit_main, "app_only_token", lambda **_: "token")
    monkeypatch.setattr(reddit_main, "fetch_listing_pages", lambda **_: [json.dumps(ended)])
    monkeypatch.setattr(
        reddit_main,
        "monthly_aggregates",
        lambda posts, reached_end, now: real_aggregates(
            posts, reached_end=reached_end, now=datetime(2025, 11, 7, tzinfo=UTC)
        ),
    )

    assert reddit_main.run([]) == 0

    db_session.expire_all()
    assert _signals(db_session, place.id, "reddit_posts_monthly") == {"2025-10": 3.0}
    # October: "Rents in Heraklion ... Airbnb" matches; the other two do not.
    assert _signals(db_session, place.id, "reddit_felt_pressure_share") == {
        "2025-10": pytest.approx(1 / 3)
    }
    archived = (
        db_session.query(SourceObservation)
        .filter(SourceObservation.dataset == "reddit_monthly")
        .order_by(SourceObservation.id.desc())
        .first()
    )
    assert "Heraklion" not in archived.raw_payload
    assert "fixture_user" not in archived.raw_payload


def test_bluesky_run_stores_counts_and_languages(db_session, place, monkeypatch) -> None:
    page = json.loads((FIXTURES / "bluesky_search_budapest_sample.json").read_text("utf-8"))
    page["cursor"] = None
    monkeypatch.setattr(bluesky_main.settings, "bluesky_handle", "tp.example.com")
    monkeypatch.setattr(bluesky_main.settings, "bluesky_app_password", "app-pass")
    monkeypatch.setattr(bluesky_main, "create_session", lambda **_: "jwt")
    monkeypatch.setattr(bluesky_main, "search_page", lambda **_: json.dumps(page))

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 11, 7)

    monkeypatch.setattr(bluesky_main, "date", FixedDate)

    assert bluesky_main.run(["--months", "1"]) == 0

    db_session.expire_all()
    assert _signals(db_session, place.id, "bluesky_posts_monthly") == {"2026-10": 3.0}
    assert _signals(db_session, place.id, "bluesky_felt_pressure_share") == {
        "2026-10": pytest.approx(1 / 3)
    }
    languages = {
        row.key: float(row.value)
        for row in db_session.query(SignalBreakdown).filter(
            SignalBreakdown.place_id == place.id,
            SignalBreakdown.signal_type == "bluesky_posts_monthly",
        )
    }
    assert languages == {"en": 1.0, "hu": 1.0, "unknown": 1.0}
    archived = (
        db_session.query(SourceObservation)
        .filter(SourceObservation.dataset == "bluesky_monthly")
        .order_by(SourceObservation.id.desc())
        .first()
    )
    assert "Christmas market" not in archived.raw_payload


def test_social_jobs_run_only_with_credentials(db_session, monkeypatch) -> None:
    for name in (
        "youtube_api_key",
        "reddit_client_id",
        "reddit_client_secret",
        "bluesky_handle",
        "bluesky_app_password",
    ):
        monkeypatch.setattr(jobs.settings, name, None)
    assert jobs.build_argv_youtube_monthly(db_session) == []
    assert jobs.build_argv_reddit(db_session) == []
    assert jobs.build_argv_bluesky(db_session) == []

    monkeypatch.setattr(jobs.settings, "youtube_api_key", "k")
    monkeypatch.setattr(jobs.settings, "reddit_client_id", "id")
    monkeypatch.setattr(jobs.settings, "reddit_client_secret", "s")
    monkeypatch.setattr(jobs.settings, "bluesky_handle", "h")
    monkeypatch.setattr(jobs.settings, "bluesky_app_password", "p")
    (youtube_argv,) = jobs.build_argv_youtube_monthly(db_session)
    assert youtube_argv[0] == "--start"
    assert jobs.build_argv_reddit(db_session) == [[]]
    assert jobs.build_argv_bluesky(db_session) == [["--months", "2"]]


def test_months_ago_crosses_the_year() -> None:
    assert jobs._months_ago(date(2026, 11, 7), 24) == "2024-11"
    assert jobs._months_ago(date(2026, 1, 15), 1) == "2025-12"
