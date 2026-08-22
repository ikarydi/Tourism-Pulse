"""Tests for YouTube's item-level path: persisting each search result
as a VideoItem row, classifying it, and deriving per-category signals -
the video counterpart to test_gdelt_item_level.py."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.classification.item_classifier import ItemCategory
from tourism_pulse_api.db.models import Destination, Place, Signal, VideoItem
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.youtube.parser import YoutubeSearchObservation, YoutubeVideo
from tourism_pulse_api.ingestion.youtube.service import (
    build_category_mentions_preview,
    count_videos_by_category,
    persist_videos,
    upsert_category_mentions_signals,
)


def make_video(
    title: str,
    *,
    video_id: str = "abc123",
    channel: str = "Some Channel",
    published_at: datetime | None = None,
) -> YoutubeVideo:
    return YoutubeVideo(video_id=video_id, title=title, channel=channel, published_at=published_at)


def make_observation(
    videos: list[YoutubeVideo], *, query: str = "Budapest travel guide"
) -> YoutubeSearchObservation:
    return YoutubeSearchObservation(
        query=query,
        total_results=len(videos),
        retrieved_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
        sample_video_titles=[v.title for v in videos[:5]],
        videos=videos,
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
    destination = Destination(country_code="HU", name="YouTube Item Level Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="YouTube Item Level Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


# --- persist_videos ------------------------------------------------------------


def test_persist_videos_creates_one_row_per_video(db_session, test_place) -> None:
    observation = make_observation(
        [
            make_video("Budapest Wine Festival highlights", video_id="v1"),
            make_video("Wildfire evacuation footage", video_id="v2"),
            make_video("Budapest Travel Guide", video_id="v3"),
        ]
    )

    rows = persist_videos(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    assert len(rows) == 3
    assert all(isinstance(row, VideoItem) for row in rows)
    assert db_session.query(VideoItem).filter(VideoItem.place_id == test_place.id).count() == 3


def test_persist_videos_tags_categories(db_session, test_place) -> None:
    observation = make_observation([make_video("Hotel prices surge amid inflation", video_id="v1")])

    rows = persist_videos(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    assert rows[0].categories == ["economic"]


def test_persist_videos_upserts_on_video_id_rather_than_duplicating(db_session, test_place) -> None:
    first = make_observation([make_video("Budapest Wine Festival", video_id="v1")])
    persist_videos(
        db_session, place_id=test_place.id, observation=first, source_observation_id=None
    )

    second = make_observation([make_video("Budapest Wine Festival - updated", video_id="v1")])
    rows = persist_videos(
        db_session, place_id=test_place.id, observation=second, source_observation_id=None
    )

    assert len(rows) == 1
    assert rows[0].title == "Budapest Wine Festival - updated"
    assert db_session.query(VideoItem).filter(VideoItem.place_id == test_place.id).count() == 1


# --- count_videos_by_category / upsert_category_mentions_signals --------------


def test_count_videos_by_category(db_session, test_place) -> None:
    observation = make_observation(
        [
            make_video("Budapest Wine Festival", video_id="v1"),
            make_video("Budapest Jazz Festival", video_id="v2"),
            make_video("Wildfire evacuation footage", video_id="v3"),
            make_video("Budapest Travel Guide", video_id="v4"),
        ]
    )
    rows = persist_videos(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    counts = count_videos_by_category(rows)

    assert counts[ItemCategory.EVENTS] == 2
    assert counts[ItemCategory.RISK] == 1
    assert counts[ItemCategory.ECONOMIC] == 0


def test_upsert_category_mentions_signals_only_writes_nonzero_categories(
    db_session, test_place
) -> None:
    observation = make_observation([make_video("Budapest Wine Festival", video_id="v1")])
    rows = persist_videos(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    results = upsert_category_mentions_signals(
        db_session,
        place_id=test_place.id,
        videos=rows,
        source_url="https://a",
        source_observation_id=None,
    )

    assert ItemCategory.EVENTS in results
    assert ItemCategory.RISK not in results

    event_signal, gate = results[ItemCategory.EVENTS]
    assert gate.accepted is True
    assert event_signal.signal_type == "video_event_mentions"
    assert event_signal.value == 1


def test_upsert_category_mentions_signals_is_idempotent(db_session, test_place) -> None:
    observation = make_observation(
        [
            make_video("Budapest Wine Festival", video_id="v1"),
            make_video("Budapest Jazz Festival", video_id="v2"),
        ]
    )
    rows = persist_videos(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    first_results = upsert_category_mentions_signals(
        db_session,
        place_id=test_place.id,
        videos=rows,
        source_url="https://a",
        source_observation_id=None,
    )
    second_results = upsert_category_mentions_signals(
        db_session,
        place_id=test_place.id,
        videos=rows,
        source_url="https://b",
        source_observation_id=None,
    )

    first_signal, _ = first_results[ItemCategory.EVENTS]
    second_signal, _ = second_results[ItemCategory.EVENTS]

    assert first_signal.id == second_signal.id
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "video_event_mentions")
        .count()
        == 1
    )


def test_build_category_mentions_preview() -> None:
    preview = build_category_mentions_preview(ItemCategory.RISK, 3)

    assert preview.target_dimension == "risk"
    assert preview.mention_count == 3
    assert 0.0 < preview.normalized_value <= 1.0
