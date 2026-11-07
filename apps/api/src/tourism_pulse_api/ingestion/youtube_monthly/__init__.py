"""Monthly YouTube upload counts per country or place.

For each month, `search.list` filtered by upload date
(`publishedAfter`/`publishedBefore`) returns an estimate of how many
videos matching "<name> travel" were uploaded that month
(`pageInfo.totalResults`). This is the one social attention series that
can be backfilled to 2016, which is why Gate 4
(research/gate4/PREREGISTRATION.md) tests it.

Each (query, month) answer is cached on disk and never fetched again, so
each month's count is frozen when first fetched: older months lose
deleted videos over time, and the live holdout must use the count taken
soon after the month closed.
"""
