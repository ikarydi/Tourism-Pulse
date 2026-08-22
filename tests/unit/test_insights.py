"""Tests for pulse.insights.build_all_dimension_evidence - connects a
dimension score to the actual signals/articles/videos/events behind it."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Event, NewsArticle, Place, Signal, VideoItem
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.pulse.calculator import PulseResult
from tourism_pulse_api.pulse.insights import build_all_dimension_evidence


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="Insights Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Insights Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def make_pulse_result(**overrides) -> PulseResult:
    defaults = dict(
        pulse=60.0, demand=60.0, capacity=60.0, events=60.0,
        environment=60.0, risk=60.0, economic=60.0,
    )
    return PulseResult(**{**defaults, **overrides})


def test_contributing_signals_grouped_by_dimension(db_session, test_place) -> None:
    now = datetime.now(UTC)
    demand_signal = Signal(
        place_id=test_place.id,
        signal_type="tourism_nights",
        value=Decimal("1000"),
        unit="nights",
        observed_at=now,
        source="ksh",
    )
    risk_signal = Signal(
        place_id=test_place.id,
        signal_type="disaster_alert_severity",
        value=Decimal("2"),
        unit="alert_score",
        observed_at=now,
        source="gdacs",
    )
    db_session.add_all([demand_signal, risk_signal])
    db_session.commit()

    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(),
        signals=[demand_signal, risk_signal],
        events=[],
    )

    assert {s.signal_type for s in evidence["demand"].contributing_signals} == {"tourism_nights"}
    assert {s.signal_type for s in evidence["risk"].contributing_signals} == {
        "disaster_alert_severity"
    }
    # Unrelated dimensions get none of these two signals.
    assert evidence["capacity"].contributing_signals == []
    assert evidence["environment"].contributing_signals == []


def test_contributing_signals_capped_and_most_recent_first(db_session, test_place) -> None:
    now = datetime.now(UTC)
    signals = [
        Signal(
            place_id=test_place.id,
            signal_type="tourism_nights",
            value=Decimal(str(i)),
            unit="nights",
            observed_at=now - timedelta(days=i),
            source="ksh",
        )
        for i in range(10)
    ]
    db_session.add_all(signals)
    db_session.commit()

    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(),
        signals=signals,
        events=[],
    )

    demand_evidence = evidence["demand"].contributing_signals
    assert len(demand_evidence) == 5
    # Most recent (i=0, smallest offset) first.
    assert demand_evidence[0].value == 0.0
    assert demand_evidence[-1].value == 4.0


def test_related_articles_matched_by_category(db_session, test_place) -> None:
    risk_article = NewsArticle(
        place_id=test_place.id,
        source="gdelt",
        url="https://a/1",
        title="Flood warning issued",
        categories=["risk"],
        retrieved_at=datetime.now(UTC),
    )
    uncategorized_article = NewsArticle(
        place_id=test_place.id,
        source="gdelt",
        url="https://a/2",
        title="Travel guide",
        categories=[],
        retrieved_at=datetime.now(UTC),
    )
    db_session.add_all([risk_article, uncategorized_article])
    db_session.commit()

    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(),
        signals=[],
        events=[],
    )

    assert [a.title for a in evidence["risk"].related_articles] == ["Flood warning issued"]
    assert evidence["demand"].related_articles == []


def test_related_videos_matched_by_category(db_session, test_place) -> None:
    video = VideoItem(
        place_id=test_place.id,
        source="youtube",
        video_id="v1",
        title="Wine Festival highlights",
        categories=["events"],
        retrieved_at=datetime.now(UTC),
    )
    db_session.add(video)
    db_session.commit()

    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(),
        signals=[],
        events=[],
    )

    assert [v.title for v in evidence["events"].related_videos] == ["Wine Festival highlights"]
    assert evidence["risk"].related_videos == []


def test_related_events_only_populated_for_events_dimension(db_session, test_place) -> None:
    event = Event(
        place_id=test_place.id,
        name="Test Festival",
        event_type="festival",
        start_at=datetime.now(UTC) + timedelta(days=10),
    )
    db_session.add(event)
    db_session.commit()

    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(),
        signals=[],
        events=[event],
    )

    assert [e.name for e in evidence["events"].related_events] == ["Test Festival"]
    assert evidence["demand"].related_events == []
    assert evidence["risk"].related_events == []


def test_evidence_carries_the_dimension_value(db_session, test_place) -> None:
    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(risk=42.0),
        signals=[],
        events=[],
    )

    assert evidence["risk"].value == 42.0


def test_all_six_dimensions_are_present(db_session, test_place) -> None:
    evidence = build_all_dimension_evidence(
        db_session,
        place_id=test_place.id,
        pulse=make_pulse_result(),
        signals=[],
        events=[],
    )

    assert set(evidence.keys()) == {
        "demand", "capacity", "events", "environment", "risk", "economic",
    }
