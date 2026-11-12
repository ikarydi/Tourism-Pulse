from datetime import UTC, date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api import licensing
from tourism_pulse_api.briefs import build_brief, find_place, render_html
from tourism_pulse_api.briefs.__main__ import main as brief_cli
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.models.forecast import LIVE
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.forecasting.service import store
from tourism_pulse_api.ingestion.eurostat_regional.parser import IndicatorValue
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.main import app
from tourism_pulse_api.public import allowed_in_public_mode
from tourism_pulse_api.settings import settings

client = TestClient(app)

# A year no other test uses, so the peer groups (indicator, year, level)
# hold exactly these four regions.
YEAR = 1991
SEASON = [2, 2, 3, 5, 9, 14, 20, 21, 12, 6, 3, 3]  # sums to 100


def _month_end(period: pd.Period) -> datetime:
    return datetime(period.year, period.month, period.days_in_month, tzinfo=UTC)


def _seed(name: str, country: str, nights_source: str = "eurostat") -> int:
    """A region `<country>01` that leads its country on every indicator,
    with two years of monthly nights and a 12-month live outlook."""
    db = SessionLocal()
    try:
        destination = Destination(country_code=country, name=f"Brief {name}")
        db.add(destination)
        db.flush()
        place = Place(
            destination_id=destination.id,
            name=name,
            place_type="region",
            nuts_code=f"{country}01",
        )
        db.add(place)
        db.flush()

        rows = []
        for position, code in enumerate(f"{country}0{n}" for n in (1, 2, 3, 4)):
            scale = 4 - position
            rows += [
                IndicatorValue(code, "tourism_intensity", YEAR, 10_000.0 * scale),
                IndicatorValue(code, "tourism_intensity", YEAR - 1, 8_000.0 * scale),
                IndicatorValue(code, "tourism_density", YEAR, 500.0 * scale),
                IndicatorValue(code, "seasonality_peak_share", YEAR, 0.08 * scale),
                IndicatorValue(code, "str_share", YEAR, 0.1 * scale),
                IndicatorValue(code, "gva_share_g_i", YEAR, 0.1 * scale),
            ]
        upsert_indicators(db, rows, source_observation_id=None, retrieved_at=datetime.now(UTC))

        months = pd.period_range("2024-07", "2026-06", freq="M")
        for month in months:
            db.add(
                Signal(
                    place_id=place.id,
                    signal_type="tourism_nights",
                    value=SEASON[month.month - 1] * 1000,
                    unit="nights",
                    observed_at=_month_end(month),
                    source=nights_source,
                )
            )
        origin = months[-1]
        store(
            db,
            [
                {
                    "place_id": place.id,
                    "signal_type": "tourism_nights",
                    "kind": LIVE,
                    "model": "POOL_GR",
                    "issued_at": datetime(2026, 9, 27, tzinfo=UTC),
                    "origin": _month_end(origin),
                    "target": _month_end(origin + horizon),
                    "horizon": horizon,
                    "point": SEASON[(origin + horizon).month - 1] * 1100,
                    "low_80": SEASON[(origin + horizon).month - 1] * 1000,
                    "high_80": SEASON[(origin + horizon).month - 1] * 1200,
                    "low_95": SEASON[(origin + horizon).month - 1] * 900,
                    "high_95": SEASON[(origin + horizon).month - 1] * 1300,
                }
                for horizon in range(1, 13)
            ],
            kind=LIVE,
        )
        db.commit()
        return place.id
    finally:
        db.close()


@pytest.fixture(scope="module")
def place_id() -> int:
    return _seed("Brief Island", "ZQ")


def _brief(place_id: int):
    db = SessionLocal()
    try:
        return build_brief(db, db.get(Place, place_id), today=date(2026, 11, 12))
    finally:
        db.close()


# --- licensing -------------------------------------------------------------


def test_only_sources_with_read_terms_are_cleared() -> None:
    assert licensing.cleared("eurostat") and licensing.cleared(" KSH ")
    assert not licensing.cleared("opensky")
    assert not licensing.cleared("youtube")
    # A source nobody has read the terms of is never cleared.
    assert licensing.licence_for("brand-new-feed").commercial_use == licensing.UNVERIFIED
    assert licensing.not_cleared({"eurostat", "opensky", "brand-new-feed"}) == [
        "brand-new-feed",
        "opensky",
    ]


def test_every_cleared_source_names_its_terms_page_and_credit() -> None:
    for source in licensing.LICENCES.values():
        if source.commercial_use == licensing.ALLOWED:
            assert source.terms_url and source.checked_on and source.attribution


# --- build -----------------------------------------------------------------


def test_brief_ranks_the_region_in_its_country_and_in_europe(place_id: int) -> None:
    brief = _brief(place_id)

    assert brief.pressure is not None
    assert brief.pressure.nuts_code == "ZQ01"
    # Top of four on every indicator: percentile 87.5 each.
    assert brief.pressure.score == 87.5
    assert brief.pressure.level == "high"
    assert brief.european_rank == 1
    assert {rank.indicator: (rank.rank, rank.regions) for rank in brief.national} == {
        indicator: (1, 4)
        for indicator in (
            "tourism_intensity",
            "tourism_density",
            "seasonality_peak_share",
            "str_share",
        )
    }
    assert [row.nuts_code for row in brief.peers] == ["ZQ01", "ZQ02", "ZQ03", "ZQ04"]
    assert [row.is_subject for row in brief.peers] == [True, False, False, False]


def test_brief_reports_trend_seasonality_and_outlook(place_id: int) -> None:
    brief = _brief(place_id)

    intensity = next(trend for trend in brief.trends if trend.indicator == "tourism_intensity")
    assert intensity.points == [(YEAR - 1, 32_000.0), (YEAR, 40_000.0)]
    assert intensity.change == pytest.approx(0.25)

    assert brief.seasonality is not None
    assert brief.seasonality.period == "2025-07 to 2026-06"
    assert brief.seasonality.peak_month == 8
    assert brief.seasonality.peak_share == pytest.approx(0.21)
    assert brief.seasonality.top3_share == pytest.approx(0.55)

    assert brief.outlook is not None
    year_ahead = next(item for item in brief.outlook["outlook"] if item["months"] == 12)
    assert year_ahead["change"] == pytest.approx(0.10)
    assert brief.outlook["validated"] is False


def test_findings_are_rule_based_sentences_with_their_figures(place_id: int) -> None:
    text = " ".join(_brief(place_id).findings)

    assert "scores 88 out of 100" in text and "high" in text
    assert "Short-term rentals account for about 40%" in text
    assert "Aug alone carries 21%" in text
    assert "+10.0% nights" in text and "not yet validated" in text
    assert "leans on visitor-facing sectors" in text


def test_brief_lists_only_cleared_sources(place_id: int) -> None:
    brief = _brief(place_id)

    assert [source.name for source in brief.sources] == ["eurostat"]
    assert brief.withheld == []


def test_sections_built_on_uncleared_sources_are_withheld() -> None:
    brief = _brief(_seed("Brief Unlicensed", "ZR", nights_source="opensky"))

    # Eurostat pressure indicators stay; nights from an uncleared source
    # take seasonality and the outlook with them.
    assert brief.pressure is not None
    assert brief.seasonality is None and brief.outlook is None
    assert len(brief.withheld) == 2 and all("opensky" in item for item in brief.withheld)
    assert [source.name for source in brief.sources] == ["eurostat"]


def test_place_without_data_gives_an_empty_brief() -> None:
    db = SessionLocal()
    try:
        destination = Destination(country_code="ZS", name="Brief empty")
        db.add(destination)
        db.flush()
        place = Place(destination_id=destination.id, name="Brief Nowhere", place_type="city")
        db.add(place)
        db.commit()
        brief = build_brief(db, place)
        html = render_html(brief)
    finally:
        db.close()

    assert brief.pressure is None and brief.findings == [] and brief.sources == []
    assert "Brief Nowhere" in html


# --- render, API, CLI ------------------------------------------------------


def test_html_is_self_contained_and_escapes_names(place_id: int) -> None:
    html = render_html(_brief(place_id), licensee="Smith & <Partners>")

    assert html.startswith("<!doctype html>")
    assert "Smith &amp; &lt;Partners&gt;" in html
    assert "http://" not in html and "<script" not in html and "<link" not in html
    for heading in (
        "Key findings",
        "Where it stands in Europe",
        "Against the rest of the country",
        "Seasonality",
        "Outlook for the next twelve months",
        "Sources and reuse",
    ):
        assert heading in html
    assert "Source: Eurostat." in html
    assert "Source: eurostat" not in html


def test_brief_endpoints(place_id: int) -> None:
    data = client.get(f"/places/{place_id}/brief")
    page = client.get(f"/places/{place_id}/brief.html")

    assert data.status_code == 200 and data.json()["pressure"]["nuts_code"] == "ZQ01"
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert client.get("/places/999999999/brief").status_code == 404


def test_cli_writes_the_file(place_id: int, tmp_path) -> None:
    out = tmp_path / "brief.html"

    assert brief_cli(["--place", "brief island", "--out", str(out)]) == 0
    assert "Brief Island" in out.read_text(encoding="utf-8")
    assert brief_cli(["--place", "no such place anywhere", "--out", str(out)]) == 1


def test_find_place_prefers_exact_name(place_id: int) -> None:
    db = SessionLocal()
    try:
        assert find_place(db, "BRIEF ISLAND").id == place_id
        assert find_place(db, "nope nope") is None
    finally:
        db.close()


# --- public mode -----------------------------------------------------------


def test_public_mode_rules() -> None:
    assert allowed_in_public_mode("GET", "/observatory")
    assert allowed_in_public_mode("GET", "/places/3/forecast")
    assert allowed_in_public_mode("POST", "/explore/query")
    assert not allowed_in_public_mode("POST", "/explore/ask")
    assert not allowed_in_public_mode("POST", "/places")
    assert not allowed_in_public_mode("DELETE", "/explore/views/1")
    assert not allowed_in_public_mode("GET", "/explore/views")
    assert not allowed_in_public_mode("GET", "/places/3/brief")
    assert not allowed_in_public_mode("GET", "/places/3/brief.html/")


def test_public_mode_refuses_writes_and_paid_content(place_id: int, monkeypatch) -> None:
    monkeypatch.setattr(settings, "public_mode", True)

    assert client.get("/observatory").status_code == 200
    assert client.get(f"/places/{place_id}/forecast").status_code == 200
    assert client.get(f"/places/{place_id}/brief").status_code == 403
    assert client.post("/places", json={"name": "x"}).status_code == 403
    assert client.post("/explore/ask", json={"question": "x"}).status_code == 403
    assert client.post("/explore/views", json={}).status_code == 403


def test_public_mode_pulse_does_not_write_snapshots(place_id: int, monkeypatch) -> None:
    from tourism_pulse_api.db.models import PulseSnapshot

    posted = client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "weather_comfort",
            "value": 85,
            "unit": "percent",
            "observed_at": "2026-08-20T10:00:00Z",
            "source": "government",
        },
    )
    assert posted.status_code == 201
    monkeypatch.setattr(settings, "public_mode", True)

    assert client.get(f"/places/{place_id}/pulse").status_code == 200
    db = SessionLocal()
    try:
        assert db.query(PulseSnapshot).filter(PulseSnapshot.place_id == place_id).count() == 0
    finally:
        db.close()


def test_writes_still_work_when_public_mode_is_off() -> None:
    assert settings.public_mode is False
    # 422, not 403: the request reaches the router and fails validation.
    assert client.post("/explore/views", json={}).status_code == 422
