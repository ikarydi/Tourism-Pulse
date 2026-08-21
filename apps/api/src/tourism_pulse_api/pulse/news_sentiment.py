"""Normalizes a GDELT news tone score into a 0-1 Pulse Engine input.

Deliberately a distinct signal_type and normalizer from the pre-existing
`"sentiment"` entry in `pulse.signal_normalization`/`pulse.normalization`
(`normalize_sentiment`) rather than reusing it: that function requires its
input already scaled to [-1, 1] at storage time, which conflicts with
this codebase's general convention of storing a signal's real raw value
(see e.g. `occupancy_rate`, stored as a raw 0-100 percentage and only
normalized at Pulse-calculation time). `news_sentiment` follows that
general convention instead - `Signal.value` holds GDELT's actual raw tone
score, and normalization happens here.

GDELT's tone score theoretically spans roughly -100 (extremely negative)
to +100 (extremely positive), but real-world news coverage rarely
exceeds roughly +/-10 - GDELT's own documentation treats `toneabs > 10`
as "fairly emotional" coverage. +/-10 is used below as the practical
"extreme" reference point past which more negative/positive tone no
longer meaningfully changes the normalized score - a considered starting
point, not a measured constant; revisit once real coverage is observed.
"""

_PRACTICAL_TONE_EXTREME = 10.0


def normalize_news_tone(tone: float) -> float:
    clamped = max(-_PRACTICAL_TONE_EXTREME, min(_PRACTICAL_TONE_EXTREME, tone))

    return (clamped + _PRACTICAL_TONE_EXTREME) / (2 * _PRACTICAL_TONE_EXTREME)
