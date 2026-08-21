"""Adapts stored `accommodation_capacity` signals into Pulse Engine inputs.

Thin, named wrapper around `pulse.seasonal_signal_adapter.process_seasonal_signal`
(see that module for why accommodation_capacity needs seasonal rather than
single-value normalization - KSH's monthly bed-place figures swing sharply
with the season, e.g. ~150k in January vs. ~500k in July). Kept as its own
module/function - rather than callers using the generic one directly - so
the type-specific guard clause and call sites stay self-documenting,
matching how `tourism_nights_adapter.py` stays separate too.
"""

from datetime import datetime

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.engine import SignalInput
from tourism_pulse_api.pulse.seasonal_signal_adapter import process_seasonal_signal

ACCOMMODATION_CAPACITY_SIGNAL_TYPE = "accommodation_capacity"


def process_capacity_signal(
    signal: Signal,
    *,
    history: list[Signal],
    now: datetime | None = None,
) -> SignalInput | None:
    """Build a seasonally-normalized SignalInput for an `accommodation_capacity` signal.

    `history` should be every `accommodation_capacity` signal available for
    the same place (the signal itself may or may not be included; it is
    excluded from its own baseline either way). Returns None - meaning this
    signal contributes nothing to the Pulse calculation - when there is not
    enough same-calendar-month history to trust a seasonal baseline, rather
    than inventing a score.
    """
    if signal.signal_type.strip().lower() != ACCOMMODATION_CAPACITY_SIGNAL_TYPE:
        raise ValueError(
            f"Expected an {ACCOMMODATION_CAPACITY_SIGNAL_TYPE!r} signal, "
            f"got {signal.signal_type!r}"
        )

    return process_seasonal_signal(signal, history=history, now=now)
