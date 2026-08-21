from tourism_pulse_api.db.models.event import Event
from tourism_pulse_api.pulse.engine import SignalInput
from tourism_pulse_api.pulse.event_impact import calculate_event_impact


EVENT_HALF_LIFE_HOURS = 12.0


def event_to_signal(
    event: Event,
    *,
    now=None,
) -> SignalInput:
    impact = calculate_event_impact(
        event_type=event.event_type,
        start_at=event.start_at,
        end_at=event.end_at,
        now=now,
    )

    return SignalInput(
        dimension="events",
        normalized_value=impact,
        age_hours=0.0,
        half_life_hours=EVENT_HALF_LIFE_HOURS,
        source="official",
    )
