from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Event, Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.events.parser import TicketmasterEvent
from tourism_pulse_api.ingestion.events.service import build_preview, upsert_event, upsert_events


def make_event(
    external_id: str = "vv123",
    *,
    name: str = "Test Festival",
    event_type: str = "festival",
    start_at: datetime = datetime(2026, 8, 28, 18, 0, tzinfo=UTC),
    end_at: datetime | None = None,
) -> TicketmasterEvent:
    return TicketmasterEvent(
        external_id=external_id,
        name=name,
        event_type=event_type,
        description="A test event.",
        start_at=start_at,
        end_at=end_at,
        source_url="https://www.ticketmaster.com/event/vv123",
        venue_name="Test Venue",
        venue_city="Budapest",
    )


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="Events Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Events Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_targets_the_events_dimension() -> None:
    preview = build_preview(make_event())

    assert preview.target_dimension == "events"
    assert preview.event_type == "festival"


def test_upsert_creates_event_with_source_metadata(db_session, test_place) -> None:
    event = make_event("vv-create-test")

    row, created = upsert_event(
        db_session,
        place_id=test_place.id,
        event=event,
        source_url="https://app.ticketmaster.com/discovery/v2/events.json?city=Budapest",
    )

    assert created is True
    assert row.place_id == test_place.id
    assert row.name == "Test Festival"
    assert row.event_type == "festival"
    assert row.source == "ticketmaster"
    assert row.external_id == "vv-create-test"
    assert row.start_at == event.start_at


def test_upsert_is_idempotent_for_the_same_external_id(db_session, test_place) -> None:
    event = make_event("vv-idempotent-test")

    first, first_created = upsert_event(
        db_session, place_id=test_place.id, event=event, source_url="https://a"
    )
    second, second_created = upsert_event(
        db_session, place_id=test_place.id, event=event, source_url="https://b"
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    count = (
        db_session.query(Event)
        .filter(Event.source == "ticketmaster", Event.external_id == "vv-idempotent-test")
        .count()
    )
    assert count == 1


def test_upsert_refreshes_fields_on_revision(db_session, test_place) -> None:
    original_start = datetime(2026, 8, 28, 18, 0, tzinfo=UTC)
    original_event = make_event("vv-revision-test", start_at=original_start)
    row, _ = upsert_event(
        db_session, place_id=test_place.id, event=original_event, source_url="https://a"
    )
    assert row.start_at == original_start

    # Ticketmaster postpones the event by a day.
    postponed_start = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)
    postponed_event = make_event("vv-revision-test", start_at=postponed_start)
    updated_row, created_again = upsert_event(
        db_session, place_id=test_place.id, event=postponed_event, source_url="https://a"
    )

    assert created_again is False
    assert updated_row.id == row.id
    assert updated_row.start_at == datetime(2026, 8, 29, 18, 0, tzinfo=UTC)


def test_manually_created_events_never_collide_with_ticketmaster_ones(
    db_session, test_place
) -> None:
    # Both have source=None, external_id=None - Postgres treats NULL as
    # distinct from NULL, so the unique constraint must not reject this.
    manual_one = Event(
        place_id=test_place.id,
        name="Manually added event",
        event_type="other",
        start_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    manual_two = Event(
        place_id=test_place.id,
        name="Another manually added event",
        event_type="other",
        start_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    db_session.add_all([manual_one, manual_two])
    db_session.commit()  # must not raise a unique-constraint violation

    assert manual_one.id != manual_two.id


def test_upsert_events_processes_a_batch(db_session, test_place) -> None:
    events = [make_event("vv1", name="Event One"), make_event("vv2", name="Event Two")]

    results = upsert_events(
        db_session, place_id=test_place.id, events=events, source_url="https://a"
    )

    assert len(results) == 2
    assert all(created for _, created in results)
    assert {row.external_id for row, _ in results} == {"vv1", "vv2"}
