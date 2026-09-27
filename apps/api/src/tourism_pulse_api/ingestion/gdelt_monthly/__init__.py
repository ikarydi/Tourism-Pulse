"""Monthly GDELT series, from the research pipeline's daily-file build.

research/nowcast/gkg.py streams GDELT's daily knowledge-graph files (the
DOC API throttles too hard for history) into monthly CSVs; this adapter
imports those outputs as signals so the app can chart them:

- countries: `gdelt_tourism_share` (articles with a tourism theme that
  mention the country, per million articles that month) and
  `gdelt_tourism_tone` (their average tone), 2017-01..2020-02 and 2022+
  (2020-03..2021-12 was skipped: COVID months, see the pre-registration);
- Hungary's KSH tourism areas: `gdelt_attention_share` (articles mentioning
  the area on any topic, per million), 2022+.

The current, incomplete month is left out. Refresh by re-running
research/nowcast/gkg.py (--phase 2 for the full span) and
gkg_regional.py, then this adapter.
"""
