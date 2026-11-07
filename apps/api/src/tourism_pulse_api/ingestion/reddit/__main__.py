"""Load Reddit monthly post counts and felt pressure for curated places.

    python -m tourism_pulse_api.ingestion.reddit
    python -m tourism_pulse_api.ingestion.reddit --dry-run

Needs REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_USER_AGENT (create
a "script" app at https://www.reddit.com/prefs/apps). Signals:
reddit_posts_monthly (posts) and reddit_felt_pressure_share (0-1).
"""

import argparse
import json
import sys
import urllib.error
from datetime import UTC, datetime

from tourism_pulse_api.ingestion.reddit.client import (
    API_BASE,
    app_only_token,
    fetch_listing_pages,
)
from tourism_pulse_api.ingestion.reddit.communities import SUBREDDITS
from tourism_pulse_api.ingestion.reddit.parser import Post, parse_listing
from tourism_pulse_api.ingestion.reddit.service import monthly_aggregates
from tourism_pulse_api.ingestion.social_monthly import MonthlyValue
from tourism_pulse_api.pulse.felt_pressure import LEXICON_VERSION
from tourism_pulse_api.settings import settings

SOURCE_NAME = "reddit"
POSTS_SIGNAL = "reddit_posts_monthly"
PRESSURE_SIGNAL = "reddit_felt_pressure_share"


def _posts_for(subreddits: tuple[str, ...], token: str, user_agent: str) -> tuple[list[Post], bool]:
    """All posts of a place's subreddits; reached_end only if every
    listing ended before the page cap."""
    posts: list[Post] = []
    reached_end = True
    oldest_per_sub: list[datetime] = []
    for subreddit in subreddits:
        try:
            pages = fetch_listing_pages(subreddit=subreddit, token=token, user_agent=user_agent)
        except urllib.error.HTTPError as exc:
            print(f"    [SKIPPED] r/{subreddit}: HTTP {exc.code}", file=sys.stderr)
            continue
        listings = [parse_listing(page) for page in pages]
        sub_posts = [post for listing in listings for post in listing.posts]
        posts.extend(sub_posts)
        if listings and listings[-1].after is not None:
            reached_end = False
            if sub_posts:
                oldest_per_sub.append(min(p.created_at for p in sub_posts))
    if oldest_per_sub:
        # Coverage is limited by the subreddit whose window is shortest:
        # drop older posts from the others so months are not half-counted.
        cutoff = max(oldest_per_sub)
        posts = [post for post in posts if post.created_at >= cutoff]
    return posts, reached_end


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.reddit")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from tourism_pulse_api.db.models import Place
    from tourism_pulse_api.db.session import SessionLocal
    from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
    from tourism_pulse_api.ingestion.social_monthly import upsert_monthly_signals

    db = SessionLocal()
    try:
        places = db.query(Place).filter(Place.name.in_(list(SUBREDDITS))).all()
        db.commit()
        if args.dry_run:
            for place in places:
                print(f"[DRY RUN] {place.name}: r/{', r/'.join(SUBREDDITS[place.name])}")
            return 0
        if not (settings.reddit_client_id and settings.reddit_client_secret):
            print("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.", file=sys.stderr)
            return 1
        user_agent = settings.reddit_user_agent
        token = app_only_token(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=user_agent,
        )
        now = datetime.now(UTC)
        values: list[MonthlyValue] = []
        archive: dict[str, list[dict[str, object]]] = {}
        for place in places:
            posts, reached_end = _posts_for(SUBREDDITS[place.name], token, user_agent)
            for aggregate in monthly_aggregates(posts, reached_end=reached_end, now=now):
                values.append(
                    MonthlyValue(place.id, POSTS_SIGNAL, aggregate.month, aggregate.posts, "posts")
                )
                values.append(
                    MonthlyValue(
                        place.id,
                        PRESSURE_SIGNAL,
                        aggregate.month,
                        aggregate.felt_pressure_share,
                        "share",
                    )
                )
                archive.setdefault(place.name, []).append(
                    {
                        "month": aggregate.month,
                        "posts": aggregate.posts,
                        "felt_pressure_share": aggregate.felt_pressure_share,
                    }
                )
            print(f"[FETCHED] {place.name}: {len(posts)} posts")
        # Only aggregates are archived: no post text or usernames are kept.
        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="reddit_monthly",
            raw_payload=json.dumps(
                {"lexicon_version": LEXICON_VERSION, "places": archive}, ensure_ascii=False
            ),
            content_type="application/json",
            source_url=API_BASE,
        )
        written = upsert_monthly_signals(
            db,
            values,
            source=SOURCE_NAME,
            source_url=API_BASE,
            source_observation_id=observation.id,
        )
        db.commit()
        print(f"[INGESTED] {written} monthly values for {len(archive)} places")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
