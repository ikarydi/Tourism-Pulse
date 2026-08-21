"""Generic adapter for signal types that need seasonal (same-calendar-month)
normalization instead of the single-value generic normalizer.

A monthly government-statistics series - KSH tourism_nights, KSH
accommodation_capacity, and any future one like it - cannot go through the
generic `signal_normalization` pipeline (`normalize_signal`) because a
single raw value (e.g. "1487 thousand nights in June") is meaningless on its
own: these series are seasonal, so a value has to be compared against the
same calendar month in prior years (see `pulse.seasonal_normalization`).
That comparison needs the place's other same-type signals, not just the one
being processed, so this adapter takes the full history explicitly rather
than fitting the single-value `Normalizer` shape used by
`signal_normalization.py`.

This keeps each raw signal (the `Signal` row, in its own natural unit, as
downloaded from the source) fully separate from the normalized 0-1 Pulse
Engine input computed here - the normalized score is never written back to
the `Signal` row.
"""

from datetime import datetime

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.engine import SignalInput
from tourism_pulse_api.pulse.seasonal_normalization import (
    STATUS_OK,
    calculate_seasonal_score,
)
from tourism_pulse_api.pulse.signal_adapter import DIMENSION_MAP
from tourism_pulse_api.pulse.signal_processing import (
    calculate_age_hours,
    get_half_life_hours,
)

# Signal types that use this seasonal path instead of signal_normalization's
# single-value normalizers. Adding a new monthly seasonal source means
# adding its signal_type here (plus DIMENSION_MAP and DEFAULT_HALF_LIFE_HOURS
# entries) - routers/pulse.py reads this set, no router changes needed.
SEASONAL_SIGNAL_TYPES: frozenset[str] = frozenset(
    {"tourism_nights", "accommodation_capacity", "accommodation_capacity_annual"}
)


def process_seasonal_signal(
    signal: Signal,
    *,
    history: list[Signal],
    now: datetime | None = None,
) -> SignalInput | None:
    """Build a seasonally-normalized SignalInput for a seasonal-type signal.

    `history` should be every signal of the same type available for the same
    place (the signal itself may or may not be included; it is excluded from
    its own baseline either way). Returns None - meaning this signal
    contributes nothing to the Pulse calculation - when there is not enough
    same-calendar-month history to trust a seasonal baseline, rather than
    inventing a score.
    """
    signal_type = signal.signal_type.strip().lower()

    if signal_type not in SEASONAL_SIGNAL_TYPES:
        raise ValueError(
            f"{signal.signal_type!r} is not a seasonal signal type. "
            f"Expected one of: {sorted(SEASONAL_SIGNAL_TYPES)}"
        )

    dimension = DIMENSION_MAP.get(signal_type)

    if dimension is None:
        raise ValueError(f"Unsupported signal type: {signal.signal_type}")

    target_month = signal.observed_at.month

    historical_values = [
        float(other.value)
        for other in history
        if other.id != signal.id
        and other.signal_type.strip().lower() == signal_type
        and other.observed_at.month == target_month
        and other.observed_at < signal.observed_at
    ]

    result = calculate_seasonal_score(float(signal.value), historical_values)

    if result.status != STATUS_OK or result.score is None:
        return None

    age_hours = calculate_age_hours(signal.observed_at, now=now)
    half_life_hours = get_half_life_hours(signal_type)

    return SignalInput(
        dimension=dimension,
        normalized_value=result.score,
        age_hours=age_hours,
        half_life_hours=half_life_hours,
        source=signal.source,
    )
