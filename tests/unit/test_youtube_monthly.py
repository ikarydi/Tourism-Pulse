import csv
import urllib.parse
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.youtube_monthly import __main__ as youtube_monthly
from tourism_pulse_api.ingestion.youtube_monthly.client import (
    monthly_request_url,
    public_source_url,
)
from tourism_pulse_api.ingestion.youtube_monthly.countries import COUNTRY_NAMES
from tourism_pulse_api.ingestion.youtube_monthly.parser import parse_total_results
from tourism_pulse_api.ingestion.youtube_monthly.service import MonthlyUploads, QuotaSpent

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "youtube_monthly_search_sample.json"


def test_contract_reads_total_results() -> None:
    assert parse_total_results(FIXTURE.read_text(encoding="utf-8")) == 4213


@pytest.mark.parametrize(
    "text", ["not json", "{}", '{"pageInfo": {}}', '{"pageInfo": {"totalResults": -1}}']
)
def test_contract_rejects_unexpected_shapes(text: str) -> None:
    with pytest.raises(ValueError):
        parse_total_results(text)


def test_request_is_filtered_to_one_upload_month() -> None:
    url = monthly_request_url(api_key="k", query="Greece travel", month="2026-12")
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert params["q"] == "Greece travel"
    assert params["type"] == "video"
    assert params["publishedAfter"] == "2026-12-01T00:00:00Z"
    assert params["publishedBefore"] == "2027-01-01T00:00:00Z"


def test_public_url_never_carries_the_key() -> None:
    assert "secret" not in public_source_url(query="Greece travel", month="2026-10")


def test_the_30_gate_countries_match_the_nowcast_data() -> None:
    nights = Path(__file__).resolve().parents[2] / "research" / "nowcast" / "data" / "nights.csv"
    with nights.open(encoding="utf-8") as handle:
        geos = {row["geo"] for row in csv.DictReader(handle)}
    assert set(COUNTRY_NAMES) == geos


def test_each_month_is_fetched_once_then_frozen(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    answers = iter(['{"pageInfo": {"totalResults": 10}}', '{"pageInfo": {"totalResults": 99}}'])

    def fetch(query: str, month: str) -> str:
        calls.append((query, month))
        return next(answers)

    uploads = MonthlyUploads(fetch, tmp_path, budget=5)
    first, _ = uploads.count("Malta travel", "2026-10")
    again, _ = MonthlyUploads(fetch, tmp_path, budget=5).count("Malta travel", "2026-10")
    assert (first, again) == (10, 10)
    assert calls == [("Malta travel", "2026-10")]


def test_budget_stops_the_run(tmp_path: Path) -> None:
    uploads = MonthlyUploads(lambda q, m: '{"pageInfo": {"totalResults": 1}}', tmp_path, budget=1)
    uploads.count("Malta travel", "2026-09")
    with pytest.raises(QuotaSpent):
        uploads.count("Malta travel", "2026-10")


def test_country_export_writes_the_gate_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        youtube_monthly,
        "fetch_month",
        lambda api_key, query, month: '{"pageInfo": {"totalResults": 7}}',
    )
    out = tmp_path / "youtube_uploads.csv"
    code = youtube_monthly.run(
        [
            "--countries",
            "--export",
            str(out),
            "--start",
            "2016-01",
            "--max-calls",
            "45",
            "--api-key",
            "k",
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert code == 2  # budget spent: 45 of many calls, the next run carries on
    assert len(rows) == 45
    assert {row["uploads"] for row in rows} == {"7"}
    # Newest month first: the run freezes the latest month for all 30
    # countries before backfilling older ones.
    assert len({row["month"] for row in rows}) == 2
