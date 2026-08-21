from datetime import datetime, timezone


EVENT_TYPE_WEIGHTS: dict[str, float] = {
    "festival": 1.00,
    "concert": 0.90,
    "sport": 0.90,
    "conference": 0.80,
    "exhibition": 0.70,
    "cultural": 0.80,
    "other": 0.50,
}


def calculate_event_impact(
    *,
    event_type: str,
    start_at: datetime,
    end_at: datetime | None = None,
    now: datetime | None = None,
) -> float:
    if now is None:
        now = datetime.now(timezone.utc)

    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)

    if end_at is not None and end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)

    if end_at is not None and end_at < start_at:
        raise ValueError("end_at cannot be before start_at")

    event_weight = EVENT_TYPE_WEIGHTS.get(
        event_type.strip().lower(),
        EVENT_TYPE_WEIGHTS["other"],
    )

    if end_at is not None and start_at <= now <= end_at:
        return event_weight

    if now < start_at:
        hours_until_start = (
            start_at - now
        ).total_seconds() / 3600

        if hours_until_start <= 24:
            return event_weight * 0.75

        if hours_until_start <= 72:
            return event_weight * 0.50

        if hours_until_start <= 168:
            return event_weight * 0.25

    return 0.0
