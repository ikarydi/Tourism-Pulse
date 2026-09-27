import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, Place, PlaceDemographics, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.explore.ask import _resolve_place_names
from tourism_pulse_api.explore.query import resolve_places, run_query
from tourism_pulse_api.ingestion.eu_locations.parser import (
    cities_with_tourism_data,
    parse_city_points,
)
from tourism_pulse_api.ingestion.eu_locations.service import (
    LocationSummary,
    ensure_city_places,
    ensure_region_places,
)
from tourism_pulse_api.ingestion.eurostat_bulk.parser import (
    AREA,
    CITY,
    COUNTRY,
    REGION,
    SERIES,
    Record,
    parse_series,
)
from tourism_pulse_api.ingestion.eurostat_bulk.service import (
    place_index,
    upsert_population,
    upsert_signals,
)
from tourism_pulse_api.ingestion.eurostat_regional.parser import IndicatorValue
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.ingestion.nuts.parser import parse_nuts_geojson
from tourism_pulse_api.ingestion.nuts.service import upsert_regions
from tourism_pulse_api.ingestion.wikipedia_monthly.__main__ import _articles_for, _summed
from tourism_pulse_api.ingestion.wikipedia_monthly.articles import Article
from tourism_pulse_api.main import app
from tourism_pulse_api.observatory.pressure import Ranker, pressure_for_codes

client = TestClient(app)


def _square(lon: float, lat: float, size: float = 1.0) -> dict:
    ring = [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def _regions(*items: tuple[str, str, int, dict]) -> None:
    text = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "NUTS_ID": code,
                        "LEVL_CODE": level,
                        "CNTR_CODE": code[:2],
                        "NAME_LATN": name,
                    },
                    "geometry": geometry,
                }
                for code, name, level, geometry in items
            ],
        }
    )
    db = SessionLocal()
    try:
        upsert_regions(db, parse_nuts_geojson(text, version="2024"))
    finally:
        db.close()


def _country(code: str, name: str) -> int:
    """A country place with its own destination, as the app's seed data has."""
    db = SessionLocal()
    try:
        existing = (
            db.query(Place).filter(Place.place_type == "country", Place.nuts_code == code).first()
        )
        if existing:
            return existing.id
        destination = Destination(country_code=code, name=name)
        db.add(destination)
        db.flush()
        place = Place(
            destination_id=destination.id, name=name, place_type="country", nuts_code=code
        )
        db.add(place)
        db.commit()
        return place.id
    finally:
        db.close()


# --- location generation ------------------------------------------------------


def test_region_and_area_places_are_generated_once_with_their_codes() -> None:
    _country("LU", "Luxembourg test")
    _regions(
        ("LU00", "Luxembourg region", 2, _square(5.0, 49.0)),
        ("LU000", "Luxembourg area", 3, _square(5.0, 49.0)),
    )
    db = SessionLocal()
    try:
        upsert_indicators(
            db,
            [
                IndicatorValue("LU00", "tourism_intensity", 2025, 1.0),
                IndicatorValue("LU000", "tourism_intensity", 2025, 1.0),
            ],
            source_observation_id=None,
        )
        for _ in range(2):  # idempotent
            ensure_region_places(db, LocationSummary())
        region = db.query(Place).filter(Place.source_code == "NUTS2:LU00").one()
        area = db.query(Place).filter(Place.source_code == "NUTS3:LU000").one()
    finally:
        db.close()

    assert (region.place_type, region.nuts_code, region.nuts3_code) == ("region", "LU00", None)
    assert (area.place_type, area.nuts_code, area.nuts3_code) == ("area", "LU00", "LU000")
    assert region.latitude is not None and 49.0 <= region.latitude <= 50.0


def test_cities_link_to_nearby_curated_destinations_instead_of_duplicating() -> None:
    _country("MT", "Malta test")
    db = SessionLocal()
    try:
        destination = Destination(country_code="MT", name="Valletta test")
        db.add(destination)
        db.flush()
        curated = Place(
            destination_id=destination.id,
            name="Valletta test",
            place_type="destination",
            latitude=35.8989,
            longitude=14.5146,
        )
        db.add(curated)
        db.commit()
        points = parse_city_points(
            json.dumps(
                {
                    "features": [
                        {
                            "properties": {
                                "URAU_CODE": "MT001C",
                                "URAU_NAME": "Valletta",
                                "CNTR_CODE": "MT",
                            },
                            "geometry": {"type": "Point", "coordinates": [14.51, 35.90]},
                        },
                        {
                            "properties": {
                                "URAU_CODE": "MT002C",
                                "URAU_NAME": "Far town",
                                "CNTR_CODE": "MT",
                            },
                            "geometry": {"type": "Point", "coordinates": [14.20, 36.05]},
                        },
                        {
                            "properties": {
                                "URAU_CODE": "CH001C",
                                "URAU_NAME": "Not EU",
                                "CNTR_CODE": "CH",
                            },
                            "geometry": {"type": "Point", "coordinates": [8.5, 47.4]},
                        },
                    ]
                }
            )
        )
        summary = LocationSummary()
        ensure_city_places(db, points, {"MT001C", "MT002C"}, summary)
        db.refresh(curated)
        created = db.query(Place).filter(Place.source_code == "URAU:MT002C").one()
    finally:
        db.close()

    assert [point.code for point in points] == ["MT001C", "MT002C"]  # non-EU dropped
    assert curated.urau_code == "MT001C"
    assert (created.place_type, created.urau_code) == ("city", "MT002C")
    assert summary.cities_created == 1


def test_cities_with_tourism_data_reads_the_city_dimension() -> None:
    payload = {
        "id": ["indic_ur", "cities", "time"],
        "size": [1, 3, 1],
        "dimension": {
            "indic_ur": {"category": {"index": {"CR2001V": 0}}},
            "cities": {"category": {"index": {"HU001C": 0, "HU": 1, "CH001C": 2}}},
            "time": {"category": {"index": {"2024": 0}}},
        },
        "value": {"0": 5.0, "1": 9.0, "2": 3.0},
    }
    assert cities_with_tourism_data(payload) == {"HU001C"}


# --- bulk Eurostat ---------------------------------------------------------------


def test_regional_monthly_series_parses_month_dimension_and_skips_totals() -> None:
    series = next(item for item in SERIES if item.key == "regional_monthly_nights")
    payload = {
        "id": ["month", "geo", "time"],
        "size": [3, 2, 1],
        "dimension": {
            "month": {"category": {"index": {"TOTAL": 0, "M01": 1, "M02": 2}}},
            "geo": {"category": {"index": {"HU11": 0, "EU27_2020": 1}}},
            "time": {"category": {"index": {"2024": 0}}},
        },
        # flat = month * 2 + geo
        "value": {"0": 999.0, "2": 10.0, "4": 20.0, "3": 5.0},
    }

    records = parse_series(series, payload)

    assert [(r.code, r.observed_at.date().isoformat(), r.value) for r in records] == [
        ("HU11", "2024-01-31", 10.0),
        ("HU11", "2024-02-29", 20.0),
    ]


def test_bulk_signals_land_only_on_the_matching_place_type() -> None:
    _country("SI", "Slovenia test")
    db = SessionLocal()
    try:
        country_destination = (
            db.query(Place).filter(Place.nuts_code == "SI", Place.place_type == "country").one()
        )
        region = Place(
            destination_id=country_destination.destination_id,
            name="SI region",
            place_type="region",
            nuts_code="SI04",
            source_code="NUTS2:SI04",
        )
        # A curated destination sharing the NUTS 2 code must not get region data.
        curated = Place(
            destination_id=country_destination.destination_id,
            name="Ljubljana test",
            place_type="destination",
            nuts_code="SI04",
            nuts3_code="SI041",
            urau_code="SI001C",
        )
        db.add_all([region, curated])
        db.commit()
        index = place_index(db)
        observed = datetime(2024, 12, 31, tzinfo=UTC)
        summary = upsert_signals(
            db,
            [
                Record("SI04", "tourism_nights_annual", "nights", observed, 100.0),
                Record("SI001C", "tourism_nights_annual", "nights", observed, 40.0),
                Record(
                    "SI04", "tourism_nights_annual", "nights", observed.replace(year=2023), -1.0
                ),
            ],
            kinds=(COUNTRY, REGION, AREA, CITY),
            source_url="test",
            source_observation_id=None,
            index=index,
        )
        values = {
            place_id: float(value)
            for place_id, value in db.query(Signal.place_id, Signal.value).filter(
                Signal.signal_type == "tourism_nights_annual",
                Signal.place_id.in_([region.id, curated.id]),
            )
        }
    finally:
        db.close()

    assert values == {region.id: 100.0, curated.id: 40.0}  # curated gets its city value only
    assert summary.invalid == 1


def test_bulk_population_upserts_by_year() -> None:
    place_id = _country("EE", "Estonia test")
    db = SessionLocal()
    try:
        index = place_index(db)
        for population in (1_300_000.0, 1_310_000.0):
            upsert_population(
                db,
                [
                    Record(
                        "EE",
                        "population",
                        "residents",
                        datetime(2024, 12, 31, tzinfo=UTC),
                        population,
                    )
                ],
                source_observation_id=None,
                index=index,
            )
        rows = db.query(PlaceDemographics).filter(PlaceDemographics.place_id == place_id).all()
    finally:
        db.close()
    assert [(row.year, row.population) for row in rows] == [(2024, 1_310_000)]


# --- attention history ------------------------------------------------------------


def test_wikipedia_articles_use_overrides_and_ksh_area_lists() -> None:
    places = [
        Place(id=1, name="Luxembourg", place_type="destination"),
        Place(id=2, name="Gyula", place_type="destination"),
        Place(
            id=3,
            name="Czechia",
            place_type="country",
            destination=Destination(country_code="CZ"),
        ),
        Place(id=4, name="Nowhere", place_type="destination"),
    ]
    resolved = {
        "Luxembourg City": {"en": "Luxembourg City", "de": "Luxemburg (Stadt)"},
        "Czechia": {
            "en": "Czech Republic",
            "de": "Tschechien",
            "cs": "Česko",
            "ja": "チェコ",
            "xx": "Not a market language",
        },
        "Nowhere": None,
    }
    with patch(
        "tourism_pulse_api.ingestion.wikipedia_monthly.__main__.resolve_titles",
        return_value=resolved,
    ):
        totals, editions, unresolved = _articles_for(places)

    # The total stays English + German, whatever else the article links to.
    assert [(a.language, a.title) for a in totals[1]] == [
        ("en", "Luxembourg City"),
        ("de", "Luxemburg (Stadt)"),
    ]
    assert ("hu", "Gyula_(Magyarország)") in [(a.language, a.title) for a in totals[2]]
    assert [(a.language, a.title) for a in totals[3]] == [
        ("en", "Czech Republic"),
        ("de", "Tschechien"),
    ]
    # Editions: market languages and the country's own, nothing else.
    assert [a.language for a in editions[3]] == ["en", "de", "cs", "ja"]
    assert unresolved == ["Nowhere"]


def test_wikipedia_breakdown_sums_a_language_only_when_every_article_reports() -> None:
    articles = [Article("de", "Bük"), Article("de", "Sárvár")]
    fetched = {
        articles[0]: {"202501": 100, "202502": 120, "209901": 5},
        articles[1]: {"202501": 40},
    }

    assert _summed(articles, fetched, current_month="202601") == {"202501": 140}


def test_bulk_ranker_matches_the_per_place_path() -> None:
    db = SessionLocal()
    try:
        upsert_indicators(
            db,
            [
                IndicatorValue("XR011", "str_share", 1998, 0.3),
                IndicatorValue("XR012", "str_share", 1998, 0.1),
                IndicatorValue("XR013", "str_share", 1998, 0.3),
                IndicatorValue("XR01", "tourism_density", 1998, 5.0),
                IndicatorValue("XR02", "tourism_density", 1998, 9.0),
            ],
            source_observation_id=None,
        )
        ranker = Ranker(db)
        for codes in (["XR011", "XR01"], ["XR012", "XR01"], ["XR02"]):
            bulk = ranker.pressure_for_codes(codes)
            single = pressure_for_codes(db, codes)
            assert bulk.score == single.score
            assert [
                (r.indicator, r.percentile, r.rank, r.region_code) for r in bulk.indicators
            ] == [(r.indicator, r.percentile, r.rank, r.region_code) for r in single.indicators]
    finally:
        db.close()


def test_region_shapes_endpoint_returns_places_with_geometry() -> None:
    _country("CY", "Cyprus test")
    _regions(("CY00", "Kypros test", 2, _square(33.0, 34.8)))
    db = SessionLocal()
    try:
        upsert_indicators(
            db, [IndicatorValue("CY00", "tourism_intensity", 2025, 1.0)], source_observation_id=None
        )
        ensure_region_places(db, LocationSummary())
    finally:
        db.close()
    from tourism_pulse_api.routers import regions

    regions._cache.clear()
    body = client.get("/regions/geojson?level=2").json()

    feature = next(item for item in body["features"] if item["properties"]["code"] == "CY00")
    assert feature["properties"]["place_id"]
    assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert client.get("/regions/geojson?level=5").status_code == 422


def test_place_type_filters_are_exact() -> None:
    db = SessionLocal()
    try:
        types = {place.place_type for place in resolve_places(db, None, "region")}
        destinations = {place.place_type for place in resolve_places(db, None, "destination")}
    finally:
        db.close()
    assert types <= {"region"}
    assert destinations <= {"destination"}


def test_ask_resolves_place_names_exact_then_prefix() -> None:
    _country("HR", "Croatia test")
    db = SessionLocal()
    try:
        exact = _resolve_place_names(db, ["croatia TEST"])
        prefix = _resolve_place_names(db, ["Croatia te"])
        nothing = _resolve_place_names(db, ["No such place anywhere"])
    finally:
        db.close()
    assert exact and exact == prefix[: len(exact)]
    assert nothing == []


@pytest.mark.parametrize("place_type", ["region", "area", "city", "destination", "country"])
def test_query_accepts_every_place_type(place_type: str) -> None:
    response = client.post(
        "/explore/query",
        json={
            "metrics": ["observatory.tourism_intensity"],
            "place_type": place_type,
            "grain": "year",
        },
    )
    assert response.status_code == 200


def test_run_query_with_region_scope_reads_indicators() -> None:
    db = SessionLocal()
    try:
        result = run_query(
            db, metric_ids=["observatory.tourism_intensity"], place_type="region", grain="year"
        )
    finally:
        db.close()
    assert all(place.place_type == "region" for place in result.places)


def test_list_all_places_includes_type_country_and_codes() -> None:
    place_id = _country("BG", "Bulgaria test")

    rows = client.get("/places").json()

    row = next(item for item in rows if item["id"] == place_id)
    assert row["place_type"] == "country"
    assert row["country_code"] == "BG"
    assert row["nuts_code"] == "BG"


def test_pulse_compares_monthly_nights_with_the_same_month_of_earlier_years() -> None:
    """Decades of monthly history are grouped by calendar month before the
    seasonal baseline is taken; each July still sees every earlier July."""
    db = SessionLocal()
    try:
        destination = Destination(country_code="ZS", name="Seasonal test")
        db.add(destination)
        db.flush()
        place = Place(destination_id=destination.id, name="Seasonal test", place_type="country")
        db.add(place)
        db.flush()
        for year, july, january in ((2023, 100.0, 50.0), (2024, 100.0, 50.0), (2025, 200.0, 50.0)):
            for month, value in ((7, july), (1, january)):
                db.add(
                    Signal(
                        place_id=place.id,
                        signal_type="tourism_nights",
                        value=value,
                        unit="nights",
                        observed_at=datetime(year, month, 28, tzinfo=UTC),
                        source="eurostat",
                    )
                )
        db.commit()
        place_id = place.id
    finally:
        db.close()

    response = TestClient(app).get(f"/places/{place_id}/pulse?persist=false")

    # Only seasonal signals: a Pulse exists only if the baselines were found.
    assert response.status_code == 200
    assert response.json()["pulse"] > 0
