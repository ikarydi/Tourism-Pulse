"""Wikipedia Pageviews ingestion - a second, independent `demand`
attention-signal source alongside YouTube's `search_interest`.

The Wikimedia REST API's per-article pageviews endpoint is fully public
and keyless - no account, no API key, no OAuth (unlike YouTube, OpenSky's
higher-quota tier, or Ticketmaster). See
https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html

Deliberately kept as its own signal_type (`wikipedia_pageviews`, see
service.py) rather than reusing YouTube's `search_interest`: both are
attention-volume signals feeding the same `demand` dimension, but a
30-day Wikipedia pageview total and a YouTube search.list totalResults
count are different orders of magnitude - sharing a signal_type would
mean sharing pulse.signal_normalization's one normalizer/reference-count
per signal_type, miscalibrating one or the other. See
pulse.wikipedia_interest for the dedicated normalizer.
"""
