"""GDELT place coverage, the Gate 2 forecast model and attention insights."""

import math
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, Forecast, Place, Signal, SignalBreakdown
from tourism_pulse_api.db.models.forecast import BACKTEST, LIVE
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.forecasting import model
from tourism_pulse_api.forecasting.read import accuracy
from tourism_pulse_api.forecasting.service import store
from tourism_pulse_api.ingestion.gdelt_gkg.parser import Matcher, Target, summarise_day, topics_of
from tourism_pulse_api.ingestion.gdelt_gkg.service import (
    MIN_DAYS,
    aggregate_months,
    monthly_values,
)
from tourism_pulse_api.insights.attention import (
    WikipediaInsight,
    highlights,
    language_mix,
    lead_lag,
)
from tourism_pulse_api.main import app
from tourism_pulse_api.scheduler.jobs import SCHEDULED_ADAPTERS

client = TestClient(app)


def _place(name: str, place_type: str = "destination", country_code: str = "HU") -> int:
    db = SessionLocal()
    try:
        destination = Destination(country_code=country_code, name=f"FA {name}")
        db.add(destination)
        db.flush()
        place = Place(destination_id=destination.id, name=name, place_type=place_type)
        db.add(place)
        db.commit()
        return place.id
    finally:
        db.close()


def _month_end(period: pd.Period) -> datetime:
    return datetime(period.year, period.month, period.days_in_month, tzinfo=UTC)


# --- GDELT: matching and daily summaries ---------------------------------------------


def _location(kind: str, name: str, fips: str, adm1: str, lat: float, lon: float) -> str:
    return f"{kind}#{name}#{fips}#{adm1}#{lat}#{lon}#1"


def test_matcher_uses_country_codes_radius_towns_and_budapest_division() -> None:
    matcher = Matcher(
        [
            Target(place_id=1, fips="HU", country=True),
            Target(place_id=2, fips="IT", latitude=45.44, longitude=12.32),  # Venice
            Target(place_id=3, fips="HU", towns=frozenset({"siofok"}), prefixes=("balaton",)),
            Target(place_id=4, fips="HU", adm1="HU05"),
        ]
    )

    near_venice = _location("4", "Mestre, Veneto, Italy", "IT", "IT20", 45.49, 12.24)
    far_from_venice = _location("4", "Verona, Veneto, Italy", "IT", "IT20", 45.44, 10.99)
    assert matcher.match(near_venice) == {2}
    assert matcher.match(far_from_venice) == set()
    # A first-order division near Venice is too coarse to count as the city.
    assert matcher.match(_location("5", "Veneto, Italy", "IT", "IT20", 45.44, 12.32)) == set()

    assert matcher.match(_location("4", "Siófok, Somogy, Hungary", "HU", "HU17", 46.9, 18.05)) == {
        1,
        3,
    }
    assert matcher.match(
        _location("4", "Balatonfüred, Veszprém, Hungary", "HU", "HU23", 46.9, 17.9)
    ) == {
        1,
        3,
    }
    assert matcher.match(
        _location("4", "Budapest, Budapest, Hungary", "HU", "HU05", 47.5, 19.08)
    ) == {
        1,
        4,
    }


def test_topics_match_names_and_prefixes() -> None:
    assert topics_of({"PROTEST", "NATURAL_DISASTER_HEAT_WAVE", "TOURISM"}) == [
        "protest",
        "disaster",
    ]
    assert topics_of({"TOURISM", "GENERAL_HEALTH"}) == []


def test_summarise_day_counts_mentions_tourism_tone_and_topics() -> None:
    venice = _location("4", "Venice, Veneto, Italy", "IT", "IT20", 45.44, 12.32)
    header = "DATE\tNUMARTS\tCOUNTS\tTHEMES\tLOCATIONS\tPERSONS\tORGS\tTONE\tCAMEO\tSOURCES\tURLS"
    lines = [
        header,
        f"20260915\t3\t\tTOURISM;PROTEST\t{venice}\t\t\t-2.0,1,3\t\tx.com\thttp://a",
        f"20260915\t2\t\tELECTION\t{venice}\t\t\t1.0,1,0\t\ty.com\thttp://b",
        "20260915\t10\t\tTOURISM;STRIKE\t\t\t\t0.0,0,0\t\tz.com\thttp://c",
    ]
    summary = summarise_day(
        "\n".join(lines), [Target(place_id=7, fips="IT", latitude=45.44, longitude=12.32)]
    )

    assert summary["corpus"] == 15
    assert summary["tourism"] == 13
    assert summary["topics"] == {"protest": 3, "strike": 10}
    counts = summary["places"]["7"]
    assert counts["mentions"] == 5
    assert counts["tourism"] == 3
    assert counts["topics"] == {"protest": 3}
    assert counts["tourism_tone"] / counts["tourism"] == -2.0
    assert counts["mention_tone"] / counts["mentions"] == (-6.0 + 2.0) / 5


def test_monthly_values_need_enough_days_and_give_shares_per_million() -> None:
    day = {
        "corpus": 1000,
        "tourism": 10,
        "topics": {},
        "places": {
            "7": {
                "mentions": 2,
                "mention_tone": -4.0,
                "tourism": 1,
                "tourism_tone": 1.0,
                "topics": {"protest": 1},
            }
        },
    }
    days = {date(2026, 3, d): day for d in range(1, MIN_DAYS + 1)}
    days |= {date(2026, 4, d): day for d in range(1, MIN_DAYS)}  # one day short
    signals, breakdowns = monthly_values(aggregate_months(days), [7])

    by_type = {row["signal_type"]: row for row in signals}
    assert {row["observed_at"].month for row in signals} == {3}
    assert by_type["gdelt_attention_share"]["value"] == 2000.0  # 2 per 1,000 articles
    assert by_type["gdelt_tourism_share"]["value"] == 1000.0
    assert by_type["gdelt_tourism_tone"]["value"] == 1.0  # 10 tourism articles, enough
    assert "gdelt_news_tone" in by_type  # 20 mentions, just enough
    assert {row["key"]: row["value"] for row in breakdowns} == {"all": 10, "protest": 10}


# --- forecasting -------------------------------------------------------------------------


def _synthetic_panel(n_places: int = 8) -> dict[int, pd.DataFrame]:
    """Nights with a seasonal shape and place-specific growth that
    Wikipedia growth announces a year ahead of time."""
    rng = np.random.default_rng(0)
    index = pd.period_range("2014-01", "2026-06", freq="M")
    season = np.array([0.6, 0.65, 0.8, 0.95, 1.1, 1.3, 1.5, 1.5, 1.2, 0.95, 0.7, 0.7])
    panel = {}
    for place in range(n_places):
        growth = 0.02 + 0.01 * place
        years = np.arange(len(index)) / 12
        y = 1e6 * (1 + place) * season[index.month - 1] * np.exp(growth * years)
        y *= np.exp(rng.normal(0, 0.01, len(index)))
        wiki = 1e5 * np.exp((growth + 0.01) * years) * np.exp(rng.normal(0, 0.01, len(index)))
        frame = pd.DataFrame({"y": y, "wiki": wiki}, index=index)
        panel[place] = frame
    return panel


def test_forecasts_follow_growth_and_cover_twelve_horizons() -> None:
    panel = _synthetic_panel()
    forecasts = model.forecast_pool(panel, models=("POOL_GR_W", "POOL_GR"))

    assert {f.horizon for f in forecasts if f.key == 3} == set(range(1, 13))
    for forecast in forecasts:
        truth_growth = 0.02 + 0.01 * forecast.key
        last_year = panel[forecast.key]["y"][forecast.target - 12]
        assert math.isclose(forecast.point / last_year, math.exp(truth_growth), rel_tol=0.03)
        assert forecast.low_80 <= forecast.point <= forecast.high_80
        assert forecast.low_95 <= forecast.low_80 and forecast.high_80 <= forecast.high_95


def test_as_of_forecasts_ignore_everything_after_the_origin() -> None:
    panel = _synthetic_panel()
    origin = pd.Period("2025-06", "M")
    before = model.forecast_pool(model.as_of(panel, origin))

    changed = {key: frame.copy() for key, frame in panel.items()}
    for frame in changed.values():
        frame.loc[frame.index > origin + model.ATTENTION_LEAD, ["y", "wiki"]] *= 5
    after = model.forecast_pool(model.as_of(changed, origin))

    assert [(f.key, f.target, round(f.point)) for f in before] == [
        (f.key, f.target, round(f.point)) for f in after
    ]
    assert all(f.origin == origin for f in before)


def _forecast_row(place_id: int, kind: str, point: float, target: pd.Period) -> dict:
    return {
        "place_id": place_id,
        "signal_type": "tourism_nights",
        "kind": kind,
        "model": "POOL_GR",
        "issued_at": datetime(2026, 9, 27, tzinfo=UTC),
        "origin": _month_end(target - 1),
        "target": _month_end(target),
        "horizon": 1,
        "point": point,
        "low_80": point * 0.9,
        "high_80": point * 1.1,
        "low_95": point * 0.8,
        "high_95": point * 1.2,
    }


def test_live_forecasts_are_never_overwritten_but_backtests_are() -> None:
    place_id = _place("Forecast store")
    target = pd.Period("2026-07", "M")
    db = SessionLocal()
    try:
        for kind in (LIVE, BACKTEST):
            store(db, [_forecast_row(place_id, kind, 100.0, target)], kind=kind)
            store(db, [_forecast_row(place_id, kind, 200.0, target)], kind=kind)
        db.commit()
        points = {
            row.kind: float(row.point)
            for row in db.query(Forecast).filter(Forecast.place_id == place_id)
        }
    finally:
        db.close()

    assert points == {LIVE: 100.0, BACKTEST: 200.0}


def test_accuracy_scores_forecasts_against_published_months() -> None:
    place_id = _place("Forecast scored", place_type="country")
    db = SessionLocal()
    try:
        store(db, [_forecast_row(place_id, LIVE, 110.0, pd.Period("2026-05", "M"))], kind=LIVE)
        store(db, [_forecast_row(place_id, LIVE, 150.0, pd.Period("2026-06", "M"))], kind=LIVE)
        db.add(
            Signal(
                place_id=place_id,
                signal_type="tourism_nights",
                value=100,
                unit="nights",
                observed_at=_month_end(pd.Period("2026-05", "M")),
                source="eurostat",
            )
        )
        db.commit()
        scored = accuracy(db, [place_id], LIVE)[place_id]
    finally:
        db.close()

    # Only May has an official figure; 110 against 100 is a 10% error,
    # just inside the 80% range (99 .. 121).
    assert scored.scored == 1
    assert math.isclose(scored.mape or 0, 0.10, rel_tol=1e-6)
    assert scored.coverage_80 == 1.0


def test_forecast_endpoint_needs_a_forecast() -> None:
    place_id = _place("No forecast")
    assert client.get(f"/places/{place_id}/forecast").status_code == 404
    assert client.get("/places/999999999/forecast").status_code == 404


# --- attention ---------------------------------------------------------------------------


def test_language_mix_compares_shares_with_the_previous_year() -> None:
    rows = []
    for month in pd.period_range("2024-09", "2026-08", freq="M"):
        recent = month > pd.Period("2025-08", "M")
        rows += [
            {"month": month, "key": "en", "value": 60.0},
            {"month": month, "key": "de", "value": 40.0 if recent else 20.0},
        ]
    mix = language_mix(pd.DataFrame(rows), pd.Period("2026-08", "M"))

    by_language = {item.language: item for item in mix}
    assert [item.language for item in mix] == ["en", "de"]
    assert math.isclose(by_language["de"].share, 0.4)
    assert math.isclose(by_language["de"].previous_share or 0, 0.25)
    assert math.isclose(by_language["de"].growth or 0, 1.0)


def test_lead_lag_finds_the_lag_at_which_interest_leads_nights() -> None:
    rng = np.random.default_rng(1)
    index = pd.period_range("2015-01", "2026-06", freq="M")
    shocks = rng.normal(0, 0.1, len(index)).cumsum()
    views = pd.Series(np.exp(shocks), index=index)
    nights = pd.Series(np.exp(np.roll(shocks, 2)), index=index)  # nights follow 2 months later

    months, correlation, observations = lead_lag(views, nights)

    assert months == 2
    assert correlation > 0.9
    assert observations >= 24


def test_highlights_read_wikipedia_against_the_typical_place() -> None:
    wiki = WikipediaInsight(
        latest_month="2026-08",
        latest_views=100.0,
        latest_vs_last_year=-0.05,
        benchmark_vs_last_year=-0.15,
        relative_to_benchmark=(0.95 / 0.85) - 1,
        views_12m=None,
        views_12m_vs_previous=None,
    )
    (line,) = highlights(wiki, None)
    assert "-5%" in line and "-15% for the median tracked place" in line
    assert "held up better than most places" in line


def test_attention_endpoint_reports_language_shares() -> None:
    place_id = _place("Attention town")
    db = SessionLocal()
    try:
        for month in pd.period_range("2024-09", "2026-08", freq="M"):
            db.add(
                Signal(
                    place_id=place_id,
                    signal_type="wikipedia_views_monthly",
                    value=1000,
                    unit="views",
                    observed_at=_month_end(month),
                    source="wikipedia",
                )
            )
            for language, views in (("en", 700), ("de", 300)):
                db.add(
                    SignalBreakdown(
                        place_id=place_id,
                        signal_type="wikipedia_views_monthly",
                        observed_at=_month_end(month),
                        dimension="language",
                        key=language,
                        value=views,
                        source="wikipedia",
                    )
                )
        db.commit()
    finally:
        db.close()

    body = client.get(f"/places/{place_id}/attention").json()

    assert body["wikipedia"]["latest_month"] == "2026-08"
    assert [
        (row["language"], round(row["share"], 2)) for row in body["wikipedia"]["languages"]
    ] == [
        ("en", 0.7),
        ("de", 0.3),
    ]


def test_bulk_jobs_and_forecasts_run_once_per_schedule() -> None:
    adapters = {adapter.name: adapter for adapter in SCHEDULED_ADAPTERS}
    for name in ("eurostat_bulk", "wikipedia_monthly", "gdelt_gkg", "forecasting"):
        assert adapters[name].build_argv(None) == [[]]  # type: ignore[arg-type]
    assert adapters["gdelt_gkg"].interval_minutes == 24 * 60
    assert adapters["forecasting"].interval_minutes == 24 * 60
