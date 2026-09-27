import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, Place, RegionalIndicator
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import eurostat_geo_code
from tourism_pulse_api.ingestion.eurostat_regional.parser import (
    IndicatorValue,
    parse_intensity_density,
    parse_seasonality,
)
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.ingestion.nuts.parser import parse_nuts_geojson
from tourism_pulse_api.ingestion.nuts.service import assign_place_nuts_codes, upsert_regions
from tourism_pulse_api.main import app
from tourism_pulse_api.observatory.pressure import pressure_for_region, pressure_level

client = TestClient(app)


def _square(lon: float, lat: float, size: float = 1.0) -> dict:
    ring = [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def _geojson(*features: tuple[str, str, dict]) -> str:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "NUTS_ID": code,
                        "LEVL_CODE": 2,
                        "CNTR_CODE": code[:2],
                        "NAME_LATN": name,
                    },
                    "geometry": geometry,
                }
                for code, name, geometry in features
            ],
        }
    )


def _jsonstat(dimensions: dict[str, list[str]], values: dict[int, float]) -> dict:
    return {
        "id": list(dimensions),
        "size": [len(categories) for categories in dimensions.values()],
        "dimension": {
            name: {"category": {"index": {code: i for i, code in enumerate(categories)}}}
            for name, categories in dimensions.items()
        },
        "value": {str(flat): value for flat, value in values.items()},
    }


def _indicators(db, rows: list[tuple[str, str, int, float]]) -> None:
    upsert_indicators(
        db,
        [IndicatorValue(code, indicator, year, value) for code, indicator, year, value in rows],
        source_observation_id=None,
        retrieved_at=datetime.now(UTC),
    )


# --- country codes --------------------------------------------------------


def test_eurostat_geo_code_maps_iso_exceptions() -> None:
    assert eurostat_geo_code("GR") == "EL"
    assert eurostat_geo_code("gb") == "UK"
    assert eurostat_geo_code("HU") == "HU"


# --- NUTS boundaries ------------------------------------------------------


def test_parse_nuts_geojson_keeps_polygons_only() -> None:
    text = _geojson(
        ("XA01", "Region A", _square(0, 0)),
        ("XA02", "Region B", {"type": "Point", "coordinates": [0, 0]}),
    )

    features = parse_nuts_geojson(text, version="2024")

    assert [feature.code for feature in features] == ["XA01"]
    assert features[0].level == 2
    assert features[0].nuts_version == "2024"


def test_parse_nuts_geojson_rejects_empty_payload() -> None:
    with pytest.raises(ValueError):
        parse_nuts_geojson('{"features": []}', version="2024")


def test_places_are_assigned_by_point_in_polygon_and_country_code() -> None:
    db = SessionLocal()
    try:
        upsert_regions(
            db,
            parse_nuts_geojson(
                _geojson(
                    ("XB01", "Inland", _square(100.0, 10.0)),
                    ("XB02", "Coast", _square(101.0, 10.0)),
                ),
                version="2024",
            ),
        )
        destination = Destination(country_code="GR", name="Test NUTS Destination")
        db.add(destination)
        db.flush()
        inside = Place(
            destination_id=destination.id,
            name="Inside",
            place_type="destination",
            latitude=10.5,
            longitude=100.5,
        )
        # ~5 km off the coast of XB02: within the nearest-region tolerance.
        offshore = Place(
            destination_id=destination.id,
            name="Offshore",
            place_type="destination",
            latitude=10.5,
            longitude=102.045,
        )
        far_away = Place(
            destination_id=destination.id,
            name="Far away",
            place_type="destination",
            latitude=-40.0,
            longitude=-100.0,
        )
        country = Place(destination_id=destination.id, name="Greece", place_type="country")
        db.add_all([inside, offshore, far_away, country])
        db.commit()

        result = assign_place_nuts_codes(db)

        db.refresh(inside)
        db.refresh(offshore)
        db.refresh(far_away)
        db.refresh(country)
        assert inside.nuts_code == "XB01"
        assert offshore.nuts_code == "XB02"
        assert far_away.nuts_code is None
        assert "Far away" in result.destinations_unmatched
        # Eurostat's national code for Greece, not ISO's GR.
        assert country.nuts_code == "EL"
    finally:
        db.close()


# --- Eurostat regional parsing ----------------------------------------------


def test_parse_intensity_density_maps_units_and_skips_aggregates() -> None:
    payload = _jsonstat(
        {
            "unit": ["P_THAB", "P_KM2"],
            "geo": ["HU11", "EU27_2020"],
            "time": ["2025"],
        },
        # flat index = unit * 2 + geo (time has one category)
        {0: 6925.2, 1: 3000.0, 2: 22896.9, 3: 100.0},
    )

    values = parse_intensity_density(payload)

    assert {(v.nuts_code, v.indicator, v.year, v.value) for v in values} == {
        ("HU11", "tourism_intensity", 2025, 6925.2),
        ("HU11", "tourism_density", 2025, 22896.9),
    }


def test_parse_seasonality_uses_complete_years_only() -> None:
    months = [f"M{m:02d}" for m in range(1, 13)]
    dimensions = {"unit": ["NR"], "month": months, "geo": ["XC01"], "time": ["2024", "2025"]}
    values = {}
    for m in range(12):
        values[m * 2 + 0] = 300.0 if m == 6 else 100.0  # 2024: July peak, complete
        if m < 11:
            values[m * 2 + 1] = 100.0  # 2025: December missing
    payload = _jsonstat(dimensions, values)

    parsed = parse_seasonality(payload)

    assert len(parsed) == 1
    assert parsed[0].year == 2024
    assert parsed[0].value == pytest.approx(300 / 1400)


def test_upsert_indicators_overwrites_in_place() -> None:
    db = SessionLocal()
    try:
        _indicators(db, [("XD01", "tourism_intensity", 1991, 10.0)])
        _indicators(db, [("XD01", "tourism_intensity", 1991, 12.5)])

        rows = (
            db.query(RegionalIndicator)
            .filter(RegionalIndicator.nuts_code == "XD01", RegionalIndicator.year == 1991)
            .all()
        )
        assert [row.value for row in rows] == [12.5]
        assert rows[0].unit == "nights_per_1000_residents"
    finally:
        db.close()


# --- ranking and score --------------------------------------------------------


def test_percentile_ranks_against_same_level_and_year_only() -> None:
    db = SessionLocal()
    try:
        _indicators(
            db,
            [
                # Five NUTS 2 peers in 1992, one of them tied with XE03.
                ("XE01", "tourism_intensity", 1992, 100.0),
                ("XE02", "tourism_intensity", 1992, 200.0),
                ("XE03", "tourism_intensity", 1992, 300.0),
                ("XE04", "tourism_intensity", 1992, 300.0),
                ("XE05", "tourism_intensity", 1992, 500.0),
                # Other level and other year: must not count as peers.
                ("XE", "tourism_intensity", 1992, 1.0),
                ("XE06", "tourism_intensity", 1991, 1.0),
                # XE03's older year: the latest year must be used.
                ("XE03", "tourism_intensity", 1990, 9999.0),
            ],
        )

        reading = pressure_for_region(db, "XE03")

        (intensity,) = reading.indicators
        assert intensity.year == 1992
        assert intensity.peers == 5
        # 2 lower + half of 2 equal, out of 5.
        assert intensity.percentile == pytest.approx(60.0)
        assert intensity.rank == 2  # only XE05 is higher
        assert reading.score == pytest.approx(60.0)
        assert reading.level == "moderate"
    finally:
        db.close()


def test_score_is_mean_of_indicator_percentiles() -> None:
    db = SessionLocal()
    try:
        _indicators(
            db,
            [
                ("XF01", "tourism_intensity", 1993, 1.0),
                ("XF02", "tourism_intensity", 1993, 2.0),
                ("XF01", "tourism_density", 1993, 9.0),
                ("XF02", "tourism_density", 1993, 1.0),
            ],
        )

        reading = pressure_for_region(db, "XF01")

        # Mid-rank percentiles (the region counts as half of its own tie):
        # lowest of 2 -> 25%, highest of 2 -> 75%.
        assert [i.percentile for i in reading.indicators] == [25.0, 75.0]
        assert reading.score == pytest.approx(50.0)
        assert reading.level == "moderate"
    finally:
        db.close()


def test_region_without_indicators_has_no_score() -> None:
    db = SessionLocal()
    try:
        reading = pressure_for_region(db, "XZ99")
        assert reading.indicators == []
        assert reading.score is None
        assert reading.level is None
    finally:
        db.close()


@pytest.mark.parametrize(
    ("score", "level"),
    [(0.0, "low"), (39.9, "low"), (40.0, "moderate"), (69.9, "moderate"), (70.0, "high")],
)
def test_pressure_level_bands(score: float, level: str) -> None:
    assert pressure_level(score) == level


# --- API ------------------------------------------------------------------


def _place_with_nuts(nuts_code: str | None) -> int:
    db = SessionLocal()
    try:
        destination = Destination(country_code="HU", name=f"Test Observatory {nuts_code}")
        db.add(destination)
        db.flush()
        place = Place(
            destination_id=destination.id,
            name=f"Observatory place {nuts_code}",
            place_type="destination",
            nuts_code=nuts_code,
        )
        db.add(place)
        db.commit()
        return place.id
    finally:
        db.close()


def test_observatory_endpoint_returns_ranked_indicators() -> None:
    db = SessionLocal()
    try:
        _indicators(
            db,
            [
                ("XG01", "tourism_intensity", 1994, 50.0),
                ("XG02", "tourism_intensity", 1994, 10.0),
            ],
        )
    finally:
        db.close()
    place_id = _place_with_nuts("XG01")

    response = client.get(f"/places/{place_id}/observatory")

    assert response.status_code == 200
    body = response.json()
    assert body["nuts_code"] == "XG01"
    assert body["score"] == pytest.approx(75.0)  # highest of 2, mid-rank
    assert body["indicators"][0]["rank"] == 1
    assert body["indicators"][0]["peers"] == 2
    assert body["method"]


def test_observatory_endpoint_without_region_is_empty_not_an_error() -> None:
    place_id = _place_with_nuts(None)

    body = client.get(f"/places/{place_id}/observatory").json()

    assert body["nuts_code"] is None
    assert body["indicators"] == []
    assert body["score"] is None


def test_observatory_endpoint_unknown_place_is_404() -> None:
    assert client.get("/places/999999/observatory").status_code == 404


def test_pulse_pressure_comes_from_the_observatory() -> None:
    db = SessionLocal()
    try:
        _indicators(
            db,
            [
                ("XH01", "tourism_intensity", 1995, 90.0),
                ("XH02", "tourism_intensity", 1995, 10.0),
            ],
        )
    finally:
        db.close()
    place_id = _place_with_nuts("XH01")
    client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "occupancy",
            "value": 70,
            "unit": "percent",
            "observed_at": datetime.now(UTC).isoformat(),
            "source": "government",
        },
    )

    pulse = client.get(f"/places/{place_id}/pulse").json()

    assert pulse["pressure"] == pytest.approx(75.0)  # highest of 2, mid-rank
    history = client.get(f"/places/{place_id}/pulse/history").json()
    assert history[0]["pressure"] == pytest.approx(75.0)
