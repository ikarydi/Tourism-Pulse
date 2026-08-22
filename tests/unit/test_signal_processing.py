from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.signal_normalization import SIGNAL_NORMALIZERS
from tourism_pulse_api.pulse.signal_processing import (
    DEFAULT_HALF_LIFE_HOURS,
    calculate_age_hours,
    get_half_life_hours,
    process_signal,
)


def make_signal(
    signal_type: str = "demand",
    observed_at: datetime | None = None,
) -> Signal:
    if observed_at is None:
        observed_at = datetime.now(UTC)

    return Signal(
        id=1,
        place_id=1,
        signal_type=signal_type,
        value=Decimal("75"),
        unit="score",
        observed_at=observed_at,
        source="government",
    )


def test_age_is_calculated_in_hours() -> None:
    now = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=UTC,
    )

    observed_at = now - timedelta(hours=6)

    assert calculate_age_hours(
        observed_at,
        now=now,
    ) == 6.0


def test_future_signal_has_zero_age() -> None:
    now = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=UTC,
    )

    observed_at = now + timedelta(hours=2)

    assert calculate_age_hours(
        observed_at,
        now=now,
    ) == 0.0


def test_naive_datetime_is_treated_as_utc() -> None:
    now = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=UTC,
    )

    observed_at = datetime(
        2026,
        8,
        20,
        6,
        0,
    )

    assert calculate_age_hours(
        observed_at,
        now=now,
    ) == 6.0


@pytest.mark.parametrize(
    ("signal_type", "expected"),
    [
        ("demand", 24.0),
        ("capacity", 48.0),
        ("event", 12.0),
        ("events", 12.0),
        ("environment", 6.0),
        ("tourism_nights", 720.0),
        ("accommodation_capacity", 720.0),
        ("occupancy_rate", 720.0),
    ],
)
def test_half_life_by_signal_type(
    signal_type: str,
    expected: float,
) -> None:
    assert get_half_life_hours(signal_type) == expected


def test_unknown_signal_type_rejected() -> None:
    with pytest.raises(ValueError):
        get_half_life_hours("unknown")


def test_every_normalizable_signal_type_has_a_half_life() -> None:
    # Regression test: every signal_type in SIGNAL_NORMALIZERS reaches
    # process_signal -> get_half_life_hours via routers/pulse.py (any
    # signal_type not in pulse.seasonal_signal_adapter.SEASONAL_SIGNAL_TYPES
    # takes this path) - a normalizer with no matching half-life entry
    # crashes the real /places/{id}/pulse endpoint with a ValueError for
    # any place that has that kind of signal (caught live: adding 11 new
    # signal_types across ingestion adapters without also registering
    # their half-life broke the pulse endpoint for real Eurostat/GDACS/
    # OpenAQ/Wikipedia/GDELT/YouTube data - none of the unit tests using
    # only the original 4 signal types could have caught it).
    missing = sorted(set(SIGNAL_NORMALIZERS) - set(DEFAULT_HALF_LIFE_HOURS))

    assert missing == []


def test_process_signal_calculates_age_and_half_life() -> None:
    now = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=UTC,
    )

    signal = make_signal(
        signal_type="occupancy",
        observed_at=now - timedelta(hours=6),
    )

    result = process_signal(
        signal,
        now=now,
    )

    assert result.dimension == "demand"
    assert result.normalized_value == 0.75
    assert result.age_hours == 6.0
    assert result.half_life_hours == 24.0
    assert result.source == "government"
def test_process_signal_does_not_modify_database_value() -> None:
    now = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=UTC,
    )

    signal = make_signal(
        signal_type="occupancy",
        observed_at=now,
    )

    original_value = signal.value

    process_signal(
        signal,
        now=now,
    )

    assert signal.value == original_value