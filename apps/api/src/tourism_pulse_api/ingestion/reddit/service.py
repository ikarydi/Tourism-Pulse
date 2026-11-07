"""Monthly aggregates from a run's posts."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from tourism_pulse_api.ingestion.reddit.parser import Post
from tourism_pulse_api.ingestion.social_monthly import month_of, month_start
from tourism_pulse_api.pulse.felt_pressure import felt_pressure_share


@dataclass(frozen=True)
class MonthAggregate:
    month: str
    posts: int
    felt_pressure_share: float


def monthly_aggregates(
    posts: list[Post], *, reached_end: bool, now: datetime
) -> list[MonthAggregate]:
    """Per month: post count and felt-pressure share.

    A month is kept only when it is complete (before the current month)
    and fully covered: the fetched posts reach back before its first day,
    or the listing ended (`reached_end`), so no older posts exist."""
    if not posts:
        return []
    oldest = min(post.created_at for post in posts)
    current = month_of(now)
    texts: dict[str, list[str]] = defaultdict(list)
    for post in posts:
        texts[month_of(post.created_at)].append(post.text)
    aggregates = []
    for month in sorted(texts):
        if month >= current:
            continue
        if not reached_end and oldest >= month_start(month):
            continue
        share = felt_pressure_share(texts[month])
        assert share is not None
        aggregates.append(MonthAggregate(month, len(texts[month]), share))
    return aggregates
