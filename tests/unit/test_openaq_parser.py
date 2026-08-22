from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.openaq.parser import (
    OPENAQ_SOURCE_NAME,
    OpenaqLocation,
    parse_openaq_latest,
    parse_openaq_locations,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture()
def locations_text() -> str:
    return (FIXTURES / "openaq_locations_budapest_sample.json").read_text(encoding="utf-8")


@pytest.fixture()
def latest_text() -> str:
    return (FIXTURES / "openaq_latest_budapest_sample.json").read_text(encoding="utf-8")


def test_parses_locations(locations_text: str) -> None:
    locations = parse_openaq_locations(locations_text)

    assert len(locations) == 2
    assert locations[0].id == 8901
    assert locations[0].name == "Budapest Kozponti"


def test_picks_out_pm25_sensor(locations_text: str) -> None:
    locations = parse_openaq_locations(locations_text)

    assert locations[0].pm25_sensor_id == 55001
    assert locations[0].pm25_unit == "µg/m³"


def test_location_without_pm25_sensor_has_none(locations_text: str) -> None:
    locations = parse_openaq_locations(locations_text)

    assert locations[1].pm25_sensor_id is None
    assert locations[1].pm25_unit is None


def test_handles_empty_results_gracefully() -> None:
    assert parse_openaq_locations('{"results": []}') == []


def test_locations_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_openaq_locations("not json")


def test_parses_latest_reading_for_matching_sensor(locations_text: str, latest_text: str) -> None:
    location = parse_openaq_locations(locations_text)[0]

    observation = parse_openaq_latest(latest_text, location=location)

    assert observation is not None
    assert observation.location_id == 8901
    assert observation.sensor_id == 55001
    assert observation.pm25_value == 14.6
    assert observation.pm25_unit == "µg/m³"


def test_latest_ignores_readings_for_other_sensors(locations_text: str, latest_text: str) -> None:
    # The fixture also contains a no2 reading (sensorsId 55002) - must not
    # be picked up as the pm25 value.
    location = parse_openaq_locations(locations_text)[0]

    observation = parse_openaq_latest(latest_text, location=location)

    assert observation is not None
    assert observation.pm25_value != 22.1


def test_latest_returns_none_when_location_has_no_pm25_sensor(latest_text: str) -> None:
    location = OpenaqLocation(id=8902, name="No PM2.5 station", pm25_sensor_id=None, pm25_unit=None)

    assert parse_openaq_latest(latest_text, location=location) is None


def test_latest_returns_none_when_sensor_has_no_reading() -> None:
    location = OpenaqLocation(id=1, name="X", pm25_sensor_id=99999, pm25_unit="µg/m³")

    assert parse_openaq_latest('{"results": []}', location=location) is None


def test_latest_invalid_json_raises_value_error(locations_text: str) -> None:
    location = parse_openaq_locations(locations_text)[0]

    with pytest.raises(ValueError):
        parse_openaq_latest("not json", location=location)


def test_negative_value_raises_value_error(locations_text: str) -> None:
    location = parse_openaq_locations(locations_text)[0]
    text = (
        '{"results": [{"datetime": {"utc": "2026-08-21T09:00:00Z"}, '
        '"value": -1, "sensorsId": 55001}]}'
    )

    with pytest.raises(ValueError):
        parse_openaq_latest(text, location=location)


def test_source_name_constant() -> None:
    assert OPENAQ_SOURCE_NAME == "openaq"
