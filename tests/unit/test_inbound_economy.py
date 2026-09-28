"""Flights, the tourism business surveys, prices, origins and dependence."""

import io
import zipfile
from datetime import UTC, date, datetime

import pandas as pd
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, Place, Signal, SignalBreakdown
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.explore.catalog import build_catalog
from tourism_pulse_api.ingestion.ec_survey.parser import parse_workbook, release_candidates
from tourism_pulse_api.ingestion.eurocontrol.parser import (
    Airport,
    airport_coordinates,
    matched_growth,
    monthly_airports,
    nearby,
)
from tourism_pulse_api.ingestion.eurostat_bulk.parser import SERIES, origin_key, parse_series
from tourism_pulse_api.ingestion.eurostat_regional.parser import IndicatorValue, sector_share
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.insights.economy import economy_for_place
from tourism_pulse_api.main import app
from tourism_pulse_api.observatory.pressure import Ranker, pressure_for_codes
from tourism_pulse_api.scheduler.jobs import SCHEDULED_ADAPTERS

client = TestClient(app)

HEADER = "YEAR,MONTH_NUM,MONTH_MON,FLT_DATE,APT_ICAO,APT_NAME,STATE_NAME,FLT_DEP_1,FLT_ARR_1\n"


def _daily(rows: list[tuple[str, str, str, int]]) -> str:
    """(date, icao, state, arrivals) -> an EUROCONTROL-style daily file."""
    return HEADER + "".join(
        f"{d[:4]},{d[5:7]},X,{d},{icao},{icao} airport,{state},{arr},{arr}\n"
        for d, icao, state, arr in rows
    )


def _month_end(period: str) -> datetime:
    month = pd.Period(period, "M")
    return datetime(month.year, month.month, month.days_in_month, tzinfo=UTC)


# --- EUROCONTROL ------------------------------------------------------------------------


def test_monthly_airports_sums_days_and_drops_an_unfinished_month() -> None:
    text = _daily(
        [
            ("2026-07-01", "LHBP", "Hungary", 100),
            ("2026-07-31", "LHBP", "Hungary", 120),
            ("2026-08-01", "LHBP", "Hungary", 90),
            ("2026-08-15", "LHBP", "Hungary", 95),  # August not finished yet
            ("2026-07-02", "LTFM", "Türkiye", 500),  # outside the EU27
        ]
    )
    monthly = monthly_airports([text])

    assert monthly[["icao", "country", "arrivals"]].values.tolist() == [["LHBP", "HU", 220]]
    assert str(monthly["month"].iloc[0]) == "2026-07"


def test_growth_counts_only_airports_reporting_in_both_years() -> None:
    rows = [
        ("2025-07-31", "LIRF", "Italy", 1000),
        ("2026-07-31", "LIRF", "Italy", 1100),
        # A newly listed airport would read as growth in a plain total.
        ("2026-07-31", "LIRQ", "Italy", 500),
    ]
    monthly = monthly_airports([_daily(rows)])

    growth = matched_growth(monthly, {"LIRF", "LIRQ"})

    assert round(growth[pd.Period("2026-07", "M")], 3) == 0.1


def test_destinations_use_nearby_airports_with_scheduled_service() -> None:
    csv = (
        "ident,icao_code,gps_code,latitude_deg,longitude_deg,scheduled_service\n"
        "LFPG,LFPG,LFPG,49.0097,2.5479,yes\n"
        "LFPB,LFPB,LFPB,48.9694,2.4414,no\n"
        "LFML,LFML,LFML,43.4393,5.2214,yes\n"
    )
    airports = airport_coordinates(csv, {"LFPG", "LFPB", "LFML"})
    gateways = {code: airport for code, airport in airports.items() if airport.scheduled}

    assert airports["LFPB"] == Airport("LFPB", 48.9694, 2.4414, False)
    assert nearby(48.8566, 2.3522, gateways, 50.0) == ["LFPG"]  # Paris, not Marseille


# --- European Commission business surveys ------------------------------------------------


def _workbook() -> bytes:
    months = pd.to_datetime(["2025-08-31", "2026-08-31"])
    sheets = {
        "55": pd.DataFrame(
            {
                "55": months,
                "SERV.HU.55.3.B.M": [-30.0, -7.0],
                "SERV.HU.55.COF.B.M": [5.0, 12.0],
                "SERV.HU.55.4.B.M": [1.0, 2.0],  # not a question we keep
                "SERV.TR.55.3.B.M": [10.0, 11.0],  # not an EU27 country
            }
        ),
        "79": pd.DataFrame({"79": months, "SERV.HU.79.3.B.M": [3.0, None]}),
    }
    book = io.BytesIO()
    with pd.ExcelWriter(book) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("services_subsectors_nsa_m_nace2.xlsx", book.getvalue())
    return archive.getvalue()


def test_survey_workbook_keeps_eu_countries_and_known_questions() -> None:
    balances = parse_workbook(_workbook())

    got = sorted((b.country, b.signal_type, f"{b.observed_at:%Y-%m}", b.value) for b in balances)
    assert got == [
        ("HU", "hotel_confidence", "2025-08", 5.0),
        ("HU", "hotel_confidence", "2026-08", 12.0),
        ("HU", "hotel_demand_expected", "2025-08", -30.0),
        ("HU", "hotel_demand_expected", "2026-08", -7.0),
        ("HU", "travel_trade_demand_expected", "2025-08", 3.0),
    ]


def test_survey_release_folders_count_back_across_the_year() -> None:
    assert release_candidates(date(2026, 2, 10), months_back=3) == ["2602", "2601", "2512", "2511"]


# --- Eurostat: prices, origins, dependence ------------------------------------------------


def _jsonstat(dims: dict[str, list[str]], values: dict[int, float]) -> dict:
    return {
        "id": list(dims),
        "size": [len(v) for v in dims.values()],
        "dimension": {
            name: {"category": {"index": {code: i for i, code in enumerate(codes)}}}
            for name, codes in dims.items()
        },
        "value": {str(k): v for k, v in values.items()},
    }


def test_price_changes_keep_negative_values() -> None:
    series = next(s for s in SERIES if s.key == "price_change")
    payload = _jsonstat(
        {
            "freq": ["M"],
            "unit": ["RCH_A"],
            "coicop18": ["TOTAL", "CP1120"],
            "geo": ["EL"],
            "time": ["2026-07"],
        },
        {0: 2.1, 1: -2.1},
    )

    records = parse_series(series, payload)

    assert sorted((r.signal_type, r.value) for r in records) == [
        ("price_change_accommodation", -2.1),
        ("price_change_all", 2.1),
    ]


def test_origins_drop_aggregates_and_the_reporting_country() -> None:
    assert origin_key("DOM") == "domestic"
    assert origin_key("CH_LI") == "CH"
    assert origin_key("EU27_2020_FOR") is None
    series = next(s for s in SERIES if s.key == "nights_by_origin")
    payload = _jsonstat(
        {
            "freq": ["A"],
            "c_resid": ["DOM", "ES", "DE", "WORLD"],
            "unit": ["NR"],
            "nace_r2": ["I551-I553"],
            "geo": ["ES"],
            "time": ["2025"],
        },
        {0: 184.0, 1: 184.0, 2: 53.0, 3: 513.0},
    )

    records = parse_series(series, payload)

    # Spain's own code repeats its domestic nights, so only DOM is kept.
    assert sorted((r.key, r.value) for r in records) == [("DE", 53.0), ("domestic", 184.0)]


def test_sector_share_divides_g_to_i_by_the_total() -> None:
    payload = _jsonstat(
        {
            "freq": ["A"],
            "unit": ["CP_MEUR"],
            "nace_r2": ["TOTAL", "G-I"],
            "geo": ["EL42", "EU27_2020"],
            "time": ["2024"],
        },
        {0: 10.0, 1: 100.0, 2: 5.0, 3: 20.0},
    )

    assert sector_share(payload, "gva_share_g_i") == [
        IndicatorValue("EL42", "gva_share_g_i", 2024, 0.5)
    ]


def test_dependence_is_ranked_but_never_part_of_the_pressure_score() -> None:
    year = 2031  # a year no other test uses, so peers are only these regions
    values = []
    for code, intensity, gva in (("QA11", 10.0, 0.10), ("QA12", 20.0, 0.30), ("QA13", 30.0, 0.50)):
        values.append(IndicatorValue(code, "tourism_intensity", year, intensity))
        values.append(IndicatorValue(code, "gva_share_g_i", year, gva))
    db = SessionLocal()
    try:
        upsert_indicators(db, values, source_observation_id=None)
        reading = pressure_for_codes(db, ["QA13"])
        ranked = Ranker(db).pressure_for_codes(["QA13"])
    finally:
        db.close()

    assert [r.indicator for r in reading.indicators] == ["tourism_intensity"]
    assert reading.score == reading.indicators[0].percentile
    assert [(r.indicator, r.rank, r.peers) for r in reading.dependence] == [("gva_share_g_i", 1, 3)]
    assert ranked.score == reading.score
    assert ranked.dependence == reading.dependence


# --- the place summary, catalog and schedule ----------------------------------------------


def _country(code: str) -> int:
    """A country place under a code no real country (or other test) uses."""
    db = SessionLocal()
    try:
        destination = Destination(country_code=code, name=f"IE country {code}")
        db.add(destination)
        db.flush()
        place = Place(
            destination_id=destination.id,
            name=f"Country {code}",
            place_type="country",
            nuts_code=code,
        )
        db.add(place)
        db.commit()
        return place.id
    finally:
        db.close()


def _signal(db, place_id: int, signal_type: str, period: str, value: float, source: str) -> None:
    db.add(
        Signal(
            place_id=place_id,
            signal_type=signal_type,
            value=value,
            unit="x",
            observed_at=_month_end(period),
            source=source,
        )
    )


def test_economy_summary_uses_own_flights_and_national_figures() -> None:
    country_id = _country("QX")
    db = SessionLocal()
    try:
        destination = Destination(country_code="QX", name="IE Larnaca")
        db.add(destination)
        db.flush()
        town = Place(destination_id=destination.id, name="Larnaca", place_type="destination")
        db.add(town)
        db.flush()
        town_id = town.id
        _signal(db, town_id, "flight_arrivals", "2026-08", 1200, "eurocontrol")
        _signal(db, town_id, "flight_arrivals_growth", "2026-08", 4.0, "eurocontrol")
        db.add(
            SignalBreakdown(
                place_id=town_id,
                signal_type="flight_arrivals",
                observed_at=_month_end("2026-08"),
                dimension="airport",
                key="LCLK",
                value=1200,
                source="eurocontrol",
            )
        )
        _signal(db, country_id, "hotel_demand_expected", "2025-08", -30, "european_commission")
        _signal(db, country_id, "hotel_demand_expected", "2026-08", -10, "european_commission")
        _signal(db, country_id, "price_change_accommodation", "2026-08", 6.0, "eurostat")
        _signal(db, country_id, "price_change_all", "2026-08", 2.0, "eurostat")
        for key, value in (("domestic", 40.0), ("UK", 30.0), ("DE", 20.0), ("QX", 40.0)):
            db.add(
                SignalBreakdown(
                    place_id=country_id,
                    signal_type="tourism_nights_annual",
                    observed_at=datetime(2025, 12, 31, tzinfo=UTC),
                    dimension="origin",
                    key=key,
                    value=value,
                    source="eurostat",
                )
            )
        db.commit()
        insight = economy_for_place(db, db.get(Place, town_id), today=date(2026, 9, 28))
    finally:
        db.close()

    assert insight.national_place_id == country_id
    assert insight.flights is not None and insight.flights.airports[0].icao == "LCLK"
    assert insight.survey is not None and not insight.survey.stale
    # An old code for the country itself is not a foreign market.
    assert [(o.key, round(o.share, 2)) for o in insight.origins.top] == [("UK", 0.6), ("DE", 0.4)]
    assert insight.highlights == [
        "Flight arrivals in August 2026: +4.0% on a year earlier at the same airports.",
        "Hotels in Country QX are more optimistic about the next three months than a year "
        "earlier: an expected-demand balance of −10 in August 2026, against −30 a year before.",
        "Accommodation prices in Country QX: +6.0% on a year earlier in August 2026, against "
        "+2.0% for all consumer prices.",
        "Largest foreign markets in 2025: United Kingdom 60%, Germany 40% of foreign nights.",
    ]

    body = client.get(f"/places/{town_id}/economy").json()
    assert body["national_place_name"] == "Country QX"
    assert body["flights"]["growth"] == 4.0


def test_a_stale_survey_is_flagged_and_left_out_of_highlights() -> None:
    country_id = _country("QY")
    db = SessionLocal()
    try:
        _signal(db, country_id, "hotel_demand_expected", "2023-09", -20, "european_commission")
        _signal(db, country_id, "hotel_demand_expected", "2024-09", -26, "european_commission")
        db.commit()
        insight = economy_for_place(db, db.get(Place, country_id), today=date(2026, 9, 28))
    finally:
        db.close()

    assert insight.survey is not None and insight.survey.stale
    assert insight.highlights == []


def test_catalog_lists_the_new_series_under_inbound_and_economy() -> None:
    country_id = _country("QZ")
    db = SessionLocal()
    try:
        _signal(db, country_id, "flight_arrivals_growth", "2026-08", 1.0, "eurocontrol")
        _signal(db, country_id, "hotel_demand_expected", "2026-08", 1.0, "european_commission")
        db.commit()
        catalog = build_catalog(db)
    finally:
        db.close()

    assert catalog["signal.flight_arrivals_growth"].group == "Inbound travel"
    assert catalog["signal.flight_arrivals_growth"].source == "EUROCONTROL"
    assert catalog["signal.hotel_demand_expected"].source == "European Commission"
    assert catalog["observatory.gva_share_g_i"].group == "Economy"


def test_flights_and_surveys_are_scheduled_weekly() -> None:
    adapters = {adapter.name: adapter for adapter in SCHEDULED_ADAPTERS}
    for name in ("eurocontrol", "ec_survey"):
        assert adapters[name].build_argv(None) == [[]]  # type: ignore[arg-type]
        assert adapters[name].interval_minutes == 7 * 24 * 60
