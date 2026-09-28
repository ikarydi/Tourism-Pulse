"""Monthly Wikipedia pageview history for countries and curated places.

The `wikipedia` adapter stores a trailing-30-day snapshot; this one
stores the full monthly series since 2015-07 (signal
`wikipedia_views_monthly`), so attention can be charted over time and set
against tourism nights. Views are summed over the place's articles:

- countries and curated destinations: the English article (titles
  resolved through the MediaWiki API, following redirects and rejecting
  disambiguation pages) and its German counterpart via language links;
- Hungary's KSH tourism areas: the Hungarian, English and German articles
  of the area's towns (the list validated for the regional nowcast study).

A month is stored only when every article reports it, and never the
current, incomplete month.
"""
