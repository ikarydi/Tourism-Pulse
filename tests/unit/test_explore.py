import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, NewsArticle, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.explore.catalog import build_catalog
from tourism_pulse_api.explore.query import UnknownMetricError, run_query
from tourism_pulse_api.ingestion.eurostat_regional.parser import IndicatorValue
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.main import app

client = TestClient(app)


def _place(name: str, *, nuts_code: str | None = None, nuts3_code: str | None = None) -> int:
    db = SessionLocal()
    try:
        destination = Destination(country_code="HU", name=f"Explore {name}")
        db.add(destination)
        db.flush()
        place = Place(
            destination_id=destination.id,
            name=name,
            place_type="destination",
            nuts_code=nuts_code,
            nuts3_code=nuts3_code,
        )
        db.add(place)
        db.commit()
        return place.id
    finally:
        db.close()


def _signals(place_id: int, signal_type: str, values: list[tuple[date, float, str, str]]) -> None:
    db = SessionLocal()
    try:
        for observed, value, unit, source in values:
            db.add(
                Signal(
                    place_id=place_id,
                    signal_type=signal_type,
                    value=value,
                    unit=unit,
                    observed_at=datetime(observed.year, observed.month, observed.day, tzinfo=UTC),
                    source=source,
                )
            )
        db.commit()
    finally:
        db.close()


def _values(result, metric: str, place_id: int) -> list[tuple[date | None, float]]:
    return [
        (row.period, row.value)
        for row in result.rows
        if row.metric == metric and row.place_id == place_id
    ]


# --- catalog --------------------------------------------------------------------


def test_catalog_lists_fixed_metrics_and_stored_signal_types() -> None:
    place_id = _place("Catalog town")
    _signals(place_id, "explore_test_signal", [(date(2025, 1, 31), 1.0, "count", "osm")])

    db = SessionLocal()
    try:
        catalog = build_catalog(db)
    finally:
        db.close()

    assert "pulse.pulse" in catalog
    assert "observatory.str_share" in catalog
    assert "signal.explore_test_signal" in catalog
    public = catalog["pulse.pulse"].public()
    assert "kind" not in public and "key" not in public


def test_catalog_endpoint_returns_metrics_and_places() -> None:
    body = client.get("/explore/catalog").json()
    assert any(metric["id"] == "pulse.pulse" for metric in body["metrics"])
    assert body["places"]


# --- query ------------------------------------------------------------------------


def test_thousand_nights_are_normalised_to_nights() -> None:
    place_id = _place("Unit town")
    _signals(place_id, "tourism_nights", [(date(2025, 3, 31), 1.5, "thousand_nights", "ksh")])

    db = SessionLocal()
    try:
        result = run_query(db, metric_ids=["signal.tourism_nights"], place_ids=[place_id])
    finally:
        db.close()

    assert _values(result, "signal.tourism_nights", place_id) == [(date(2025, 3, 1), 1500.0)]


def test_sources_reporting_the_same_moment_are_averaged_not_summed() -> None:
    place_id = _place("Two source town")
    _signals(
        place_id,
        "tourism_nights",
        [
            (date(2025, 4, 30), 100.0, "nights", "eurostat"),
            (date(2025, 4, 30), 300.0, "nights", "ksh_test"),
        ],
    )

    db = SessionLocal()
    try:
        result = run_query(db, metric_ids=["signal.tourism_nights"], place_ids=[place_id])
    finally:
        db.close()

    assert _values(result, "signal.tourism_nights", place_id) == [(date(2025, 4, 1), 200.0)]


def test_yearly_sums_need_all_twelve_months() -> None:
    place_id = _place("Partial year town")
    full_year = [(date(2024, month, 28), 10.0, "nights", "eurostat") for month in range(1, 13)]
    partial_year = [(date(2025, month, 28), 10.0, "nights", "eurostat") for month in range(1, 6)]
    _signals(place_id, "tourism_nights", full_year + partial_year)

    db = SessionLocal()
    try:
        result = run_query(
            db, metric_ids=["signal.tourism_nights"], place_ids=[place_id], grain="year"
        )
    finally:
        db.close()

    assert _values(result, "signal.tourism_nights", place_id) == [(date(2024, 1, 1), 120.0)]
    assert any("fewer than 12 months" in note for note in result.notes)


def test_averaged_metrics_keep_partial_periods() -> None:
    place_id = _place("Weather town")
    _signals(
        place_id,
        "temperature",
        [
            (date(2025, 7, 1), 20.0, "celsius", "open-meteo"),
            (date(2025, 7, 2), 30.0, "celsius", "open-meteo"),
        ],
    )

    db = SessionLocal()
    try:
        result = run_query(
            db, metric_ids=["signal.temperature"], place_ids=[place_id], grain="year"
        )
    finally:
        db.close()

    assert _values(result, "signal.temperature", place_id) == [(date(2025, 1, 1), 25.0)]
    assert result.notes == []


def test_indicators_follow_the_place_to_its_finest_region() -> None:
    place_id = _place("Indicator town", nuts_code="XP01", nuts3_code="XP011")
    db = SessionLocal()
    try:
        upsert_indicators(
            db,
            [
                IndicatorValue("XP011", "str_share", 2025, 0.4),
                IndicatorValue("XP01", "str_share", 2025, 0.1),
                IndicatorValue("XP01", "tourism_density", 2025, 900.0),
            ],
            source_observation_id=None,
        )
        result = run_query(
            db,
            metric_ids=["observatory.str_share", "observatory.tourism_density"],
            place_ids=[place_id],
            grain="year",
        )
    finally:
        db.close()

    assert _values(result, "observatory.str_share", place_id) == [(date(2025, 1, 1), 0.4)]
    assert _values(result, "observatory.tourism_density", place_id) == [(date(2025, 1, 1), 900.0)]


def test_count_metrics_count_rows_per_period() -> None:
    place_id = _place("News town")
    db = SessionLocal()
    try:
        for index, day in enumerate((3, 9, 20)):
            db.add(
                NewsArticle(
                    place_id=place_id,
                    source="gdelt",
                    url=f"https://example.test/{place_id}/{index}",
                    title="Story",
                    published_at=datetime(2025, 6, day, tzinfo=UTC),
                    categories=[],
                    retrieved_at=datetime.now(UTC),
                )
            )
        db.commit()
        result = run_query(db, metric_ids=["count.news_articles"], place_ids=[place_id])
    finally:
        db.close()

    assert _values(result, "count.news_articles", place_id) == [(date(2025, 6, 1), 3.0)]


def test_date_range_filters_periods() -> None:
    place_id = _place("Range town")
    _signals(
        place_id,
        "temperature",
        [
            (date(2024, 1, 5), 1.0, "celsius", "open-meteo"),
            (date(2025, 1, 5), 2.0, "celsius", "open-meteo"),
        ],
    )

    db = SessionLocal()
    try:
        result = run_query(
            db, metric_ids=["signal.temperature"], place_ids=[place_id], start=date(2025, 1, 1)
        )
    finally:
        db.close()

    assert _values(result, "signal.temperature", place_id) == [(date(2025, 1, 1), 2.0)]


def test_unknown_or_too_many_metrics_are_rejected() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(UnknownMetricError):
            run_query(db, metric_ids=["signal.does_not_exist"])
        with pytest.raises(UnknownMetricError):
            run_query(
                db, metric_ids=["pulse.pulse"] * 2 + ["pulse.demand", "pulse.risk", "pulse.events"]
            )
    finally:
        db.close()


def test_query_endpoint_returns_rows_freshness_and_422_for_unknown_metric() -> None:
    place_id = _place("Endpoint town")
    _signals(place_id, "temperature", [(date(2025, 8, 15), 25.0, "celsius", "open-meteo")])

    response = client.post(
        "/explore/query", json={"metrics": ["signal.temperature"], "places": [place_id]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [
        {
            "metric": "signal.temperature",
            "place_id": place_id,
            "period": "2025-08-01",
            "value": 25.0,
        }
    ]
    assert body["data_through"] == "2025-08-01"
    assert [place["id"] for place in body["places"]] == [place_id]

    bad = client.post("/explore/query", json={"metrics": ["signal.nope"]})
    assert bad.status_code == 422


# --- saved views ----------------------------------------------------------------


def _spec(metrics: list[str]) -> dict:
    return {
        "query": {"metrics": metrics, "grain": "year"},
        "chart": {"type": "bar", "x": "place", "collapse": "latest"},
    }


def test_saved_view_lifecycle() -> None:
    created = client.post(
        "/explore/views", json={"title": "Rental share", "spec": _spec(["observatory.str_share"])}
    )
    assert created.status_code == 201
    view = created.json()
    assert view["pinned"] is True
    assert view["spec"]["chart"]["type"] == "bar"

    second = client.post(
        "/explore/views", json={"title": "Pulse", "spec": _spec(["pulse.pulse"])}
    ).json()
    assert second["position"] > view["position"]

    updated = client.put(
        f"/explore/views/{view['id']}", json={"title": "Rental share by city", "pinned": False}
    ).json()
    assert updated["title"] == "Rental share by city"
    assert updated["pinned"] is False

    ids = [item["id"] for item in client.get("/explore/views").json()]
    assert view["id"] in ids and second["id"] in ids

    assert client.delete(f"/explore/views/{view['id']}").status_code == 204
    assert client.put(f"/explore/views/{view['id']}", json={"title": "x"}).status_code == 404


def test_saved_view_rejects_unknown_metrics() -> None:
    response = client.post(
        "/explore/views", json={"title": "Bad", "spec": _spec(["signal.not_a_metric"])}
    )
    assert response.status_code == 422


# --- ask ------------------------------------------------------------------------


def _llm_reply(payload: dict):
    message = SimpleNamespace(content=json.dumps(payload))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_ask_without_llm_provider_is_503() -> None:
    with patch("tourism_pulse_api.explore.ask.settings.groq_api_key", None):
        response = client.post("/explore/ask", json={"question": "rental share by city"})
    assert response.status_code == 503


def test_ask_returns_a_validated_spec_and_drops_unknown_places() -> None:
    reply = _llm_reply(
        {
            "title": "Short-term rental share by city",
            "explanation": "Latest platform share per city.",
            "spec": {
                "query": {
                    "metrics": ["observatory.str_share"],
                    "places": [987654],
                    "grain": "year",
                },
                "chart": {"type": "bar", "x": "place", "collapse": "latest"},
            },
        }
    )
    with (
        patch("tourism_pulse_api.explore.ask.settings.groq_api_key", "test-key"),
        patch("tourism_pulse_api.explore.ask.Groq") as groq,
    ):
        groq.return_value.chat.completions.create.return_value = reply
        response = client.post("/explore/ask", json={"question": "rental share by city"})

    assert response.status_code == 200
    body = response.json()
    assert body["spec"]["query"]["metrics"] == ["observatory.str_share"]
    assert body["spec"]["query"]["places"] is None  # 987654 does not exist
    assert body["title"] == "Short-term rental share by city"


def test_ask_rejects_metrics_outside_the_catalog() -> None:
    reply = _llm_reply(
        {"title": "x", "explanation": "", "spec": {"query": {"metrics": ["signal.invented"]}}}
    )
    with (
        patch("tourism_pulse_api.explore.ask.settings.groq_api_key", "test-key"),
        patch("tourism_pulse_api.explore.ask.Groq") as groq,
    ):
        groq.return_value.chat.completions.create.return_value = reply
        response = client.post("/explore/ask", json={"question": "something odd"})

    assert response.status_code == 422
