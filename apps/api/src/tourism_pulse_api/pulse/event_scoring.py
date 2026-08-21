from datetime import datetime, timezone

from tourism_pulse_api.db.models.event import Event


def calculate_event_score(
    event: Event,
    *,
    now: datetime | None = None,
) -> float:
    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    start_at = event.start_at
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)

    end_at = event.end_at
    if end_at is not None and end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)

    if end_at is not None and start_at <= now <= end_at:
        return 1.0

    hours_until_start = (
        start_at - now
    ).total_seconds() / 3600

    if hours_until_start < 0:
        return 0.0

    if hours_until_start <= 24:
        return 0.8

    if hours_until_start <= 72:
        return 0.5

    return 0.2
