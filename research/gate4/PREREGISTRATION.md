# Gate 4: does social attention improve forecasts 4–12 months ahead?

Pre-registered on 2026-11-07, before any social media data was fetched.
Follows Gate 2 (`research/forecast/`), whose shipped model POOL_GR_WG is
the baseline here, and Gate 3 (`research/gate3/`).

No YouTube, Reddit, Bluesky or Google Trends data had been retrieved for
any country or place when this file was written. The adapters that will
fetch them were written in the same change and tested only on
hand-made fixtures.

## Question

Gate 2 found that open attention data (Wikipedia pageviews and GDELT news
coverage) lowers forecast error 4–12 months ahead, by 3–5%, while adding
nothing at 1–3 months. Social media is another place where people show
interest in a destination before they travel. Gate 4 asks whether one
social attention source, added to POOL_GR_WG, lowers forecast error further
at horizons 4–12.

Only YouTube is tested. It is the one social source whose history can be
retrieved back to 2016 through an official API (search filtered by upload
date). Reddit's listings stop at about 1,000 posts and Bluesky starts in
2023, so both are collected forward and reported descriptively (Part 2).
Google Trends is not tested here: access to its API was not available on
the registration date. If it becomes available, it gets its own
pre-registration.

## Data (fixed)

Unchanged from Gate 2, in `research/nowcast/data/`: `nights.csv`,
`pageviews.csv`, `gdelt_full.csv` (30 countries: EU27 + CH, IS, NO).

New, in `research/gate4/data/`, built by
`python -m tourism_pulse_api.ingestion.youtube_monthly --countries --export research/gate4/data/youtube_uploads.csv`
and committed with its retrieval date before any model is fitted:

- `youtube_uploads.csv`: for each of the 30 countries and each month from
  2016-01 to the last complete month, `pageInfo.totalResults` of a
  YouTube Data API v3 `search.list` call with `q = "<English country
  name> travel"`, `type = video`, `publishedAfter` = the first day of the
  month and `publishedBefore` = the first day of the next month (UTC),
  `maxResults = 1`. One call per country and month; no retries that
  change the query.

The query wording is fixed here and is not tuned. Country names are the
English short names in `ingestion/youtube_monthly/countries.py`, committed
with this file (Czechia, not Czech Republic).

## Set-up

Everything in Gate 2's set-up holds: origin `o` is the last month with an
official figure, target `t = o + h`, attention measured over `a-2 … a`
with `a = o + 1`, forecasts in logs and reported in nights, direct pooled
regressions per horizon fitted on all countries' rows with target ≤ `o`,
and the same COVID exclusion (2020-03 to 2021-12).

New feature, built exactly like Gate 2's `wiki`:

- **`yt`, YouTube upload growth**: the mean over `a-2 … a` of
  `log((u_m + 1) / (u_{m-12} + 1))`, where `u_m` is the month's upload
  count. A cell gets `yt` only when all six months are present.

## Models

| Name | Regressors |
|---|---|
| WG | `gbar`, `wiki`, `gdelt`, `tone`: Gate 2's shipped model, the baseline |
| WG_Y | WG plus `yt` |

Descriptive only, never used for a decision:

| Name | Definition |
|---|---|
| G_Y | POOL_GR (`gbar` only) plus `yt`: does YouTube stand in for Wikipedia and GDELT? |

80% intervals are the 10% and 90% quantiles of training residuals, as in
Gate 2. Horizons 1–12 are all computed. Decisions use horizons 4–12.

## Known weakness of the data, stated in advance

YouTube's `totalResults` is an estimate, and videos deleted since upload
are missing from today's counts. Older months may therefore be
undercounted relative to recent ones. Year-on-year growth removes a
constant bias but not a bias that grows with age. To limit this:

- the development period uses only targets from 2023-07, as in Gates 2
  and 3;
- the decisive test is the **live holdout** below, where each month's
  count is fetched once, within 10 days of the month closing, and frozen.

A country is dropped from the gate, before any model is fitted, if more
than 10% of its months report `totalResults` of exactly 0 or exactly
1,000,000 (YouTube's cap). Dropped countries are listed in the results.

## Periods

- **Development**: targets 2023-07 to 2026-06, on the backfilled counts.
  The baseline's errors on these months are known from Gates 2 and 3; the
  new regressor has never been evaluated.
- **Live holdout**: forecasts issued from origins `o` from 2026-09 (the
  last month published by Eurostat at registration) onward, with targets
  up to 2027-12, using `yt` from the frozen month-by-month fetches only.
  Scored once, after Eurostat has published 2027-12 for all eligible
  countries (expected around March 2028).

The development result is reported as soon as it is computed but cannot
pass or fail the gate on its own.

## Scoring

- MASE per country as in Gate 2 (scale: mean absolute seasonal
  difference, 2016-01 to 2019-12), averaged over the cells with
  `4 ≤ h ≤ 12`.
- Any comparison of two models uses only the cells both forecast.
- A country is **eligible** if both models forecast at least 75% of its
  holdout cells with `4 ≤ h ≤ 12`.
- 80% interval coverage pooled over eligible countries, `4 ≤ h ≤ 12`.
- Descriptive: MAPE by horizon 1–12, the same comparison at `h ≤ 3`, and
  a two-sided sign test across countries.

## Gate criteria (live holdout, `4 ≤ h ≤ 12`)

With `n` eligible countries:

- **G4-A YouTube: pass** if WG_Y beats WG (MASE ratio < 1) in at least
  `⌊n/2⌋ + 1` countries **and** the median ratio is ≤ 0.97.
- **G4-B calibration: pass** if WG_Y's 80% intervals cover between 70% and
  90% of eligible holdout outcomes at `4 ≤ h ≤ 12`.

## What each outcome means for the product

- **G4-A pass**: WG_Y becomes a new model version for horizons 4–12. WG
  keeps being issued as a stored shadow. Published forecasts are never
  rewritten.
- **G4-A fail**: WG stays. YouTube, Reddit and Bluesky stay in the app as
  context (felt pressure and attention), with no claim that they improve
  forecasts.
- G4-B fail with G4-A pass: recalibrate the intervals by split-conformal
  scaling of log errors on development, as Gate 2 pre-registered, and
  report it.
- Kill rule: if, after six scored target months, WG_Y's live `4 ≤ h ≤ 12`
  MASE is worse than the shadow's, production reverts to WG.
- Until the live holdout is scored, no copy, pitch or paper may claim that
  social media data improves forecasts.

## Part 2 (descriptive): felt pressure

For the curated places with a Reddit community or Bluesky coverage, the
app records monthly post counts and the share of posts matching a fixed
crowding, price and short-term-let lexicon (`pulse/felt_pressure.py`,
committed with this file). Once 24 months exist, report the correlation
between each place's felt-pressure share and its tourism intensity
(nights per resident) by month. This is description, not a gate, and no
product decision depends on it.
