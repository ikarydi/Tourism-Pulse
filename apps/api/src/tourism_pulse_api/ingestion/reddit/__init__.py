"""Reddit: monthly post counts and felt pressure for places with their own
community (r/budapest, r/crete, ...).

Uses Reddit's official Data API with an app-only OAuth token (free for
non-commercial use; a paid product needs Reddit's commercial terms). A
subreddit's `new` listing returns at most about 1,000 posts, so there is
no deep history: a month is stored only when the posts fetched reach back
past its first day, and the weekly scheduled run fills each month as it
closes. Post text is read in memory for the felt-pressure lexicon and
never stored (see ingestion.social_monthly).
"""
