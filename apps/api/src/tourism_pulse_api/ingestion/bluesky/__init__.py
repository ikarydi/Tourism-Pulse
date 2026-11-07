"""Bluesky: monthly post counts, felt pressure and language mix per place.

Uses the AT Protocol's `app.bsky.feed.searchPosts` with an app password
(Settings > App passwords in the Bluesky app), for posts naming the place
in a calendar month. A month is stored only when the search was paged to
its end; a month with more posts than the page cap is skipped rather than
undercounted. Bluesky's history starts in 2023, so this series is
collected forward. Post text is read in memory and never stored (see
ingestion.social_monthly).
"""
