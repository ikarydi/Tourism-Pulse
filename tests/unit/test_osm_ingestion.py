"""Tests for OpenStreetMap hotel/restaurant ingestion.

Real-fixture happy path (a live Overpass response) plus hand-built edge
cases: nameless POIs skipped, way/relation `center` coordinate extraction,
error responses, and the service layer's overwrite-in-place idempotency.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.db.models import Attraction, Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.osm.client import build_overpass_query
from tourism_pulse_api.ingestion.osm.parser import (
    HOTEL_CATEGORY,
    OSM_SOURCE_NAME,
    RESTAURANT_CATEGORY,
    OsmPoi,
    parse_overpass_pois,
    parse_overpass_timestamp,
)
from tourism_pulse_api.ingestion.osm.service import (
    build_preview,
    upsert_attraction,
    upsert_poi_count_signal,
)
from tourism_pulse_api.pulse.poi_density import (
    HOTEL_REFERENCE_COUNT,
    normalize_hotel_count,
    normalize_restaurant_count,
)

HOTELS_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "overpass_hotels_budapest_sample.json"
)


# --- client: query building ---------------------------------------------


def test_build_overpass_query_includes_tag_and_around_filter() -> None:
    query = build_overpass_query(category="hotel", latitude=47.4979, longitude=19.0402, radius_meters=5000)

    assert 'tourism"="hotel"' in query
    assert "around:5000,47.4979,19.0402" in query


def test_build_overpass_query_rejects_unknown_category() -> None:
    with pytest.raises(ValueError):
        build_overpass_query(category="museum", latitude=0, longitude=0)


# --- parsing: real fixture ------------------------------------------------


def test_parses_all_named_pois_from_real_fixture() -> None:
    pois = parse_overpass_pois(HOTELS_FIXTURE.read_text(encoding="utf-8"), category=HOTEL_CATEGORY)

    assert len(pois) == 5
    assert all(poi.category == HOTEL_CATEGORY for poi in pois)
    assert all(poi.name for poi in pois)


def test_parsed_pois_have_coordinates_from_node_lat_lon() -> None:
    pois = parse_overpass_pois(HOTELS_FIXTURE.read_text(encoding="utf-8"), category=HOTEL_CATEGORY)

    assert all(poi.latitude is not None and poi.longitude is not None for poi in pois)


def test_external_id_is_stable_and_type_prefixed() -> None:
    pois = parse_overpass_pois(HOTELS_FIXTURE.read_text(encoding="utf-8"), category=HOTEL_CATEGORY)

    ikonik = next(poi for poi in pois if poi.name == "Ikonik Parlament")
    assert ikonik.external_id == "node/262861756"


def test_parse_overpass_timestamp_reads_osm3s_snapshot_time() -> None:
    observed_at = parse_overpass_timestamp(HOTELS_FIXTURE.read_text(encoding="utf-8"))

    assert observed_at is not None
    assert observed_at.year == 2026
    assert observed_at.month == 8


# --- parsing: hand-built edge cases ---------------------------------------


def test_nameless_elements_are_skipped() -> None:
    text = json.dumps(
        {
            "osm3s": {"timestamp_osm_base": "2026-01-01T00:00:00Z"},
            "elements": [
                {"type": "node", "id": 1, "lat": 47.5, "lon": 19.0, "tags": {"tourism": "hotel"}},
                {"type": "node", "id": 2, "lat": 47.6, "lon": 19.1, "tags": {"tourism": "hotel", "name": "Named Hotel"}},
            ],
        }
    )

    pois = parse_overpass_pois(text, category=HOTEL_CATEGORY)

    assert len(pois) == 1
    assert pois[0].name == "Named Hotel"


def test_way_element_uses_center_for_coordinates() -> None:
    text = json.dumps(
        {
            "elements": [
                {
                    "type": "way",
                    "id": 99,
                    "center": {"lat": 47.51, "lon": 19.04},
                    "tags": {"tourism": "hotel", "name": "Big Building Hotel"},
                },
            ],
        }
    )

    pois = parse_overpass_pois(text, category=HOTEL_CATEGORY)

    assert pois[0].latitude == 47.51
    assert pois[0].longitude == 19.04
    assert pois[0].external_id == "way/99"


def test_element_with_no_coordinates_at_all_gets_none() -> None:
    text = json.dumps(
        {"elements": [{"type": "relation", "id": 5, "tags": {"amenity": "restaurant", "name": "Mystery Spot"}}]}
    )

    pois = parse_overpass_pois(text, category=RESTAURANT_CATEGORY)

    assert pois[0].latitude is None
    assert pois[0].longitude is None


def test_invalid_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_overpass_pois("not json", category=HOTEL_CATEGORY)


def test_error_response_raises() -> None:
    text = json.dumps({"remark": "runtime error: something went wrong"})

    with pytest.raises(ValueError):
        parse_overpass_pois(text, category=HOTEL_CATEGORY)


def test_parse_overpass_timestamp_returns_none_when_absent() -> None:
    assert parse_overpass_timestamp(json.dumps({"elements": []})) is None


# --- normalization ---------------------------------------------------------


def test_normalize_hotel_count_zero_is_zero() -> None:
    assert normalize_hotel_count(0) == 0.0


def test_normalize_hotel_count_at_reference_is_near_one() -> None:
    assert normalize_hotel_count(HOTEL_REFERENCE_COUNT) == pytest.approx(1.0)


def test_normalize_hotel_count_caps_at_one_above_reference() -> None:
    assert normalize_hotel_count(HOTEL_REFERENCE_COUNT * 10) == 1.0


def test_normalize_restaurant_count_matches_its_own_reference() -> None:
    # Same shape, different (higher) reference than hotels.
    assert normalize_restaurant_count(200) < normalize_hotel_count(200)


def test_normalize_rewards_early_growth_more_than_marginal_growth() -> None:
    # Going from 0->20 should gain more score than going from 100->120,
    # per the log-saturating curve's documented diminishing-returns intent.
    early_gain = normalize_hotel_count(20) - normalize_hotel_count(0)
    late_gain = normalize_hotel_count(120) - normalize_hotel_count(100)

    assert early_gain > late_gain


# --- service: preview -------------------------------------------------------


def test_build_preview_reports_count_and_normalized_value() -> None:
    pois = [
        OsmPoi(osm_type="node", osm_id=i, category=HOTEL_CATEGORY, name=f"Hotel {i}", latitude=47.5, longitude=19.0, description=None)
        for i in range(10)
    ]

    preview = build_preview(pois, category=HOTEL_CATEGORY, reference_count=HOTEL_REFERENCE_COUNT)

    assert preview.poi_count == 10
    assert preview.target_dimension == "capacity"
    assert len(preview.sample_names) == 5


# --- service: DB ingestion ---------------------------------------------------


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="OSM Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(destination_id=destination.id, name="OSM Ingestion Test Place", place_type="destination")
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def make_poi(osm_id: int, *, category: str = HOTEL_CATEGORY, name: str | None = None) -> OsmPoi:
    return OsmPoi(
        osm_type="node",
        osm_id=osm_id,
        category=category,
        name=name or f"POI {osm_id}",
        latitude=47.5,
        longitude=19.0,
        description="Test description",
    )


def test_upsert_attraction_creates_row(db_session, test_place) -> None:
    poi = make_poi(100_001)

    attraction, created = upsert_attraction(db_session, place_id=test_place.id, poi=poi)

    assert created is True
    assert attraction.name == poi.name
    assert attraction.category == HOTEL_CATEGORY
    assert attraction.source == OSM_SOURCE_NAME
    assert attraction.external_id == "node/100001"


def test_upsert_attraction_is_idempotent(db_session, test_place) -> None:
    poi = make_poi(100_002)

    first, first_created = upsert_attraction(db_session, place_id=test_place.id, poi=poi)
    second, second_created = upsert_attraction(db_session, place_id=test_place.id, poi=poi)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert db_session.query(Attraction).filter(Attraction.place_id == test_place.id).count() == 1


def test_upsert_attraction_refreshes_stale_fields(db_session, test_place) -> None:
    poi = make_poi(100_003, name="Old Name")
    upsert_attraction(db_session, place_id=test_place.id, poi=poi)

    renamed = make_poi(100_003, name="New Name")
    updated, created = upsert_attraction(db_session, place_id=test_place.id, poi=renamed)

    assert created is False
    assert updated.name == "New Name"


def test_upsert_poi_count_signal_creates_row(db_session, test_place) -> None:
    signal, gate = upsert_poi_count_signal(
        db_session, place_id=test_place.id, category=HOTEL_CATEGORY, poi_count=42
    )

    assert signal.signal_type == "hotel_count"
    assert signal.value == 42
    assert signal.source == OSM_SOURCE_NAME
    assert gate.accepted is True


def test_upsert_poi_count_signal_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    # Deliberately different from the seasonal adapters: OSM has no
    # "periods" to keep history of, so repeated runs must not pile up
    # rows (that would dilute the Pulse dimension average).
    first, _ = upsert_poi_count_signal(
        db_session, place_id=test_place.id, category=HOTEL_CATEGORY, poi_count=10
    )
    second, _ = upsert_poi_count_signal(
        db_session, place_id=test_place.id, category=HOTEL_CATEGORY, poi_count=15
    )

    assert first.id == second.id
    assert second.value == 15
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "hotel_count")
        .count()
        == 1
    )


def test_hotel_and_restaurant_counts_are_independent_signals(db_session, test_place) -> None:
    hotel_signal, _ = upsert_poi_count_signal(
        db_session, place_id=test_place.id, category=HOTEL_CATEGORY, poi_count=10
    )
    restaurant_signal, _ = upsert_poi_count_signal(
        db_session, place_id=test_place.id, category=RESTAURANT_CATEGORY, poi_count=50
    )

    assert hotel_signal.id != restaurant_signal.id
    assert hotel_signal.signal_type == "hotel_count"
    assert restaurant_signal.signal_type == "restaurant_count"


def test_upsert_poi_count_signal_rejects_unknown_category(db_session, test_place) -> None:
    with pytest.raises(ValueError):
        upsert_poi_count_signal(db_session, place_id=test_place.id, category="museum", poi_count=1)


def test_upsert_poi_count_signal_records_source_observation_id(db_session, test_place) -> None:
    source = db_session.query(Source).filter(Source.name == "osm").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="overpass_hotel",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_poi_count_signal(
        db_session,
        place_id=test_place.id,
        category=HOTEL_CATEGORY,
        poi_count=10,
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_poi_count_signal_rejects_negative_count(db_session, test_place) -> None:
    signal, gate = upsert_poi_count_signal(
        db_session, place_id=test_place.id, category=HOTEL_CATEGORY, poi_count=-1
    )

    assert signal is None
    assert gate.accepted is False
