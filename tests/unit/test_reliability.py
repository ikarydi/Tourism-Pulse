from tourism_pulse_api.pulse.reliability import (
    SOURCE_RELIABILITY,
    get_source_reliability,
)


def test_government_source_is_highest_reliability() -> None:
    assert get_source_reliability("government") == 1.0


def test_official_source_is_highest_reliability() -> None:
    assert get_source_reliability("official") == 1.0


def test_ksh_source_is_highest_reliability() -> None:
    assert get_source_reliability("ksh") == 1.0


def test_airport_reliability() -> None:
    assert get_source_reliability("airport") == 0.98


def test_hotel_reliability() -> None:
    assert get_source_reliability("hotel") == 0.95


def test_news_reliability() -> None:
    assert get_source_reliability("news") == 0.85


def test_social_reliability() -> None:
    assert get_source_reliability("social") == 0.65


def test_unknown_source() -> None:
    assert get_source_reliability("something_unknown") == 0.40


def test_source_is_case_insensitive() -> None:
    assert get_source_reliability("Government") == 1.0


def test_source_whitespace_is_ignored() -> None:
    assert get_source_reliability("  airport  ") == 0.98


def test_all_reliabilities_are_valid() -> None:
    assert all(
        0.0 <= reliability <= 1.0
        for reliability in SOURCE_RELIABILITY.values()
    )
