"""Adapts stored `tourism_nights` signals into Pulse Engine inputs.

Thin, named wrapper around `pulse.seasonal_signal_adapter.process_seasonal_signal`
(see that module for why tourism_nights needs seasonal rather than
single-value normalization). Kept as its own module/function - rather than
callers using the generic one directly - so the type-specific guard clause
and call sites stay self-documenting, matching how `event_adapter.py` stays
separate from `signal_adapter.py`.
"""

from datetime import datetime

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.engine import SignalInput
from tourism_pulse_api.pulse.seasonal_signal_adapter import process_seasonal_signal

TOURISM_NIGHTS_SIGNAL_TYPE = "tourism_nights"


def process_tourism_nights_signal(
    signal: Signal,
    *,
    history: list[Signal],
    now: datetime | None = None,
) -> SignalInput | None:
    """Build a seasonally-normalized SignalInput for a `tourism_nights` signal.

    `history` should be every `tourism_nights` signal available for the same
    place (the signal itself may or may not be included; it is excluded from
    its own baseline either way). Returns None - meaning this signal
    contributes nothing to the Pulse calculation - when there is not enough
    same-calendar-month history to trust a seasonal baseline, rather than
    inventing a score.
    """
    if signal.signal_type.strip().lower() != TOURISM_NIGHTS_SIGNAL_TYPE:
        raise ValueError(
            f"Expected a {TOURISM_NIGHTS_SIGNAL_TYPE!r} signal, "
            f"got {signal.signal_type!r}"
        )

    return process_seasonal_signal(signal, history=history, now=now)
