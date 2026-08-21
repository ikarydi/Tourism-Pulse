from decimal import Decimal
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.ksh.parser import (
    KSH_SOURCE_NAME,
    NIGHTS_UNIT,
    SUPPORTED_REGIONS,
    latest_observation,
    parse_ksh_csv,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ksh_tur0081_sample.csv"
)

BUDAPEST = ["budapest"]


@pytest.fixture()
def sample_csv_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _csv(*rows: str) -> str:
    title = "27.2.1.19. Tourism nights;" + ";" * 39
    header = ";".join(["Year", "Month"] + [f"col{i}" for i in range(39)])
    return "\n".join([title, header, *rows])


def _row(year: str, month: str, domestic_budapest: str, international_budapest: str) -> str:
    domestic = ["1"] * 13
    domestic[2] = domestic_budapest
    international = ["1"] * 13
    international[2] = international_budapest
    total = ["1"] * 13
    fields = [year, month] + domestic + international + total
    return ";".join(fields)


def test_parses_only_budapest_total_section(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    # The commercial/private decoy sections use domestic 999 / 555 -
    # none of that should leak into the parsed total-section observations.
    assert all(o.domestic_nights not in (Decimal(999), Decimal(555)) for o in observations)


def test_domestic_and_international_are_distinguished(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    june_2025 = next(o for o in observations if o.period == "2025-06")

    assert june_2025.domestic_nights == Decimal(158)
    assert june_2025.international_nights == Decimal(901)


def test_total_is_calculated_as_domestic_plus_international(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    june_2025 = next(o for o in observations if o.period == "2025-06")

    assert june_2025.total_nights == june_2025.domestic_nights + june_2025.international_nights
    assert june_2025.total_nights == Decimal(1059)


def test_month_parsing_produces_correct_year_month_and_bounds(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    june_2026 = next(o for o in observations if o.period == "2026-06")

    assert june_2026.year == 2026
    assert june_2026.month == 6
    assert june_2026.period_start.isoformat() == "2026-06-01"
    assert june_2026.period_end.isoformat() == "2026-06-30"


def test_unpublished_months_are_skipped_not_invented(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    periods = {o.period for o in observations}

    assert "2026-07" not in periods
    assert "2026-08" not in periods


def test_year_over_year_percentage_rows_are_not_parsed_as_observations(
    sample_csv_text: str,
) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    june_2026_observations = [o for o in observations if o.period == "2026-06"]

    assert len(june_2026_observations) == 1
    assert june_2026_observations[0].total_nights == Decimal(1059)


def test_january_june_summary_rows_are_skipped(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    assert len(observations) == 36
    assert all(1 <= o.month <= 12 for o in observations)


def test_observations_are_sorted_chronologically(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    periods = [(o.year, o.month) for o in observations]

    assert periods == sorted(periods)


def test_unit_and_place_name(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    assert all(o.unit == NIGHTS_UNIT for o in observations)
    assert all(o.place_name == "Budapest" for o in observations)
    assert all(o.region == "budapest" for o in observations)


def test_latest_observation_helper(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=BUDAPEST)

    assert latest_observation(observations).period == "2026-06"


def test_latest_observation_of_empty_list_is_none() -> None:
    assert latest_observation([]) is None


def test_empty_csv_returns_empty_list() -> None:
    assert parse_ksh_csv("", regions=BUDAPEST) == []


def test_source_name_constant() -> None:
    assert KSH_SOURCE_NAME == "ksh"


def test_non_numeric_value_is_skipped_not_crashed() -> None:
    text = _csv(
        "Nights at tourist accommodation establishments, thousands;" + ";" * 39,
        _row("2026", "June", "n.a.", "150"),
    )

    assert parse_ksh_csv(text, regions=BUDAPEST) == []


def test_blank_value_is_skipped_not_invented() -> None:
    text = _csv(
        "Nights at tourist accommodation establishments, thousands;" + ";" * 39,
        _row("2026", "June", "", "150"),
    )

    assert parse_ksh_csv(text, regions=BUDAPEST) == []


def test_thousands_separator_is_stripped() -> None:
    text = _csv(
        "Nights at tourist accommodation establishments, thousands;" + ";" * 39,
        _row("2026", "June", "1 234", "5 678"),
    )

    observations = parse_ksh_csv(text, regions=BUDAPEST)

    assert len(observations) == 1
    assert observations[0].domestic_nights == Decimal(1234)
    assert observations[0].international_nights == Decimal(5678)


def test_rows_before_the_total_section_are_ignored() -> None:
    text = _csv(
        "Nights at commercial accommodation establishments, thousands;" + ";" * 39,
        _row("2026", "June", "999", "999"),
    )

    assert parse_ksh_csv(text, regions=BUDAPEST) == []


def test_too_short_rows_are_ignored() -> None:
    text = _csv(
        "Nights at tourist accommodation establishments, thousands;" + ";" * 39,
        "2026;June;1;2;3",
    )

    assert parse_ksh_csv(text, regions=BUDAPEST) == []


# --- multi-region selection -------------------------------------------------


def test_default_regions_returns_every_supported_region(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text)

    regions_seen = {o.region for o in observations}

    assert regions_seen == set(SUPPORTED_REGIONS)


def test_balaton_column_is_selected_independently_of_budapest(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=["balaton"])

    june_2025 = next(o for o in observations if o.period == "2025-06")

    assert june_2025.region == "balaton"
    assert june_2025.place_name == "Balaton"
    assert june_2025.domestic_nights == Decimal(525)
    assert june_2025.international_nights == Decimal(210)
    assert june_2025.total_nights == Decimal(735)


def test_debrecen_column_is_selected_independently_of_budapest(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=["debrecen"])

    june_2025 = next(o for o in observations if o.period == "2025-06")

    assert june_2025.region == "debrecen"
    assert june_2025.place_name == "Debrecen"
    assert june_2025.domestic_nights == Decimal(102)
    assert june_2025.international_nights == Decimal(45)
    assert june_2025.total_nights == Decimal(147)


def test_requesting_multiple_regions_returns_all_of_them(sample_csv_text: str) -> None:
    observations = parse_ksh_csv(sample_csv_text, regions=["budapest", "balaton", "debrecen"])

    regions_seen = {o.region for o in observations}

    assert regions_seen == {"budapest", "balaton", "debrecen"}
    # 36 published months per region (see test_january_june_summary_rows_are_skipped)
    assert len(observations) == 36 * 3


def test_unsupported_region_raises() -> None:
    with pytest.raises(ValueError):
        parse_ksh_csv("irrelevant", regions=["atlantis"])


def test_supported_regions_cover_every_ksh_tourism_area() -> None:
    assert SUPPORTED_REGIONS.keys() == {
        "balaton",
        "budapest",
        "greater_budapest",
        "buk_sarvar",
        "debrecen",
        "gyor_pannonhalma",
        "gyula",
        "eger",
        "pecs",
        "sopron",
        "szeged",
        "tokaj_nyiregyhaza",
    }
