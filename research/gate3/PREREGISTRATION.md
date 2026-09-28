# Gate 3: do flights and the hotel survey improve forecasts 1–3 months ahead?

Pre-registered on 2026-09-28, before any Gate 3 forecast was computed.
Follows Gate 2 (`research/forecast/`), whose shipped model POOL_GR_WG is
the baseline here.

Before this file was written, the new data were examined only for
coverage: which countries and months exist, which airports report, and the
latest values of the survey's confidence indicator. No relationship between
the new data and nights was computed.

## Question

Gate 2 found that Wikipedia and GDELT improve forecasts 4–12 months ahead
but add nothing at 1–3 months. Two official sources are published before
Eurostat's nights for the same month and may cover that gap:

1. **Flights.** Eurocontrol counts every IFR flight at 377 European
   airports each day and publishes a month's figures within about four
   weeks. Eurostat's nights for the same month arrive two to three months
   after it ends.
2. **Hotel survey.** Each month the European Commission asks accommodation
   firms (NACE 55) how they expect demand to change over the next three
   months, and publishes the answer within the month.

Gate 3 asks whether each source, added to POOL_GR_WG, lowers forecast error
at horizons 1–3.

## Data (fixed)

Unchanged from Gate 2, in `research/nowcast/data/`: `nights.csv`,
`pageviews.csv`, `gdelt_full.csv` (30 countries: EU27 + CH, IS, NO).

New, in `research/gate3/data/`, built by `python -m research.gate3.fetch`
and retrieved 2026-09-28 (`RETRIEVED_AT`):

- `flights.csv`: IFR arrivals and departures per airport and month
  (Eurocontrol daily file `FLT_ARR_1`, `FLT_DEP_1`, summed), 2016-01 to
  2026-08, for airports in the 30 countries.
- `hotel_survey.csv`: services survey, accommodation (NACE 55), monthly
  balances not seasonally adjusted, 26 countries (no Luxembourg; no
  CH, IS, NO). Spain stops at 2024-09, Estonia and Malta at 2026-04.

No other data are added after this file is committed, except the Part 2
national series below, which are retrieved and committed before Part 2 is
run.

## Set-up

Everything in Gate 2's set-up holds: origin `o` is the last month with an
official figure, target `t = o + h`, attention measured over
`a-2 … a` with `a = o + 1`, forecasts in logs and reported in nights,
direct pooled regressions per horizon fitted on all countries' rows with
target ≤ `o`, and the same COVID exclusion (any row whose target, base
year, or feature months or their year-earlier months fall in 2020-03 to
2021-12 is left out of training and evaluation).

New features, both measured at the single month `a = o + 1` (the same
information date as attention in Gate 2):

- **`fl`, flight growth**: `log(Σ arrivals_a / Σ arrivals_{a-12})`, summed
  over the country's airports that report arrivals in both months.
  Eurocontrol's airport list grows over time (Italy from 13 to 49
  airports, Norway from 5 to 43), so only airports present in both years
  count.
- **`sv`, expected demand**: the survey balance for expected demand over
  the next three months at `a`, minus the same balance at `a − 12`,
  divided by 100. The year-on-year difference removes the survey's
  seasonal pattern, as the target is itself a year-on-year change.

Both are available at `a = o + 1` in practice: when Eurostat publishes
month `o`, Eurocontrol has published `o + 1` and the survey has published
`o + 1` and usually `o + 2`.

## Models

All extend POOL_GR_WG (`gbar`, `wiki`, `gdelt`, `tone`):

| Name | Extra regressors |
|---|---|
| WG | none: Gate 2's shipped model, the baseline |
| WG_F | `fl` |
| WG_S | `sv` |
| WG_FS | `fl`, `sv` |

Descriptive only, never used for a decision:

| Name | Definition |
|---|---|
| WG_S2 | WG_S with `sv` measured at `o + 2`, the survey's usual availability |
| GR_F | POOL_GR (`gbar` only) plus `fl`: does flight data stand in for attention? |

A model forecasts a cell only when all its regressors exist for that cell.
80% intervals are the 10% and 90% quantiles of training residuals, as in
Gate 2. Horizons 1–12 are all computed. Decisions use horizons 1–3.

## Periods

- **Development**: targets 2023-07 to 2025-06.
- **Holdout**: targets 2025-07 to 2026-06. Run once, after the selection
  below is committed.

These are Gate 2's periods. Gate 2 already scored WG on the holdout, so
the baseline's holdout errors are known. The new regressors have never
been evaluated on any period. The live record that follows this gate is
the clean test.

## Scoring

- MASE per country as in Gate 2 (scale: mean absolute seasonal difference,
  2016-01 to 2019-12), averaged over the cells with `h ≤ 3`.
- Any comparison of two models uses only the cells both forecast.
- A country is **eligible** for a comparison if both models forecast at
  least 75% of its holdout cells with `h ≤ 3`.
- 80% interval coverage pooled over eligible countries, `h ≤ 3`.
- Descriptive: MAPE by horizon 1–12, the same comparisons at `h = 4–12`,
  and a two-sided sign test across countries.

## Selection on development (committed before the holdout)

- **BEST_T**: of WG_F, WG_S and WG_FS, the lowest mean MASE at `h ≤ 3`
  across countries, on the three models' common sample.

## Gate criteria (holdout, `h ≤ 3`)

With `n` eligible countries for each comparison:

- **G3-A flights: pass** if WG_F beats WG (MASE ratio < 1) in at least
  `⌊n/2⌋ + 1` countries **and** the median ratio is ≤ 0.97.
- **G3-B survey: pass** if WG_S beats WG in at least `⌊n/2⌋ + 1`
  countries **and** the median ratio is ≤ 0.97.
- **G3-C calibration: pass** if the shipped model's 80% intervals cover
  between 70% and 90% of eligible holdout outcomes at `h ≤ 3`.

## What each outcome means for the product

- **Which model ships at `h ≤ 3`**: BEST_T, if every source it uses passed
  its gate. Otherwise the single-source model whose gate passed. If neither
  passed, WG stays. Horizons 4–12 stay WG in every case.
- A country missing a new source uses the nested model without it, as
  production already does for attention.
- If a new model ships, the app keeps issuing WG's `h ≤ 3` forecasts as a
  stored shadow, so the live record compares the two. Live forecasts
  already issued are never rewritten.
- G3-C fail: recalibrate the intervals on development by split-conformal
  scaling of log errors, as Gate 2 pre-registered, and report it.
- Kill rule: if, after six scored target months, the shipped model's live
  `h ≤ 3` MASE is worse than the shadow's, production reverts to WG.
- If neither gate passes, flights and the survey stay in the app as data
  and context beside the outlook, with no claim that they improve it.

## Part 2 (descriptive): national surveys

Three countries publish monthly visitor figures before Eurostat. With one
country each, these are case studies, not gates.

| Country | Series | Information date |
|---|---|---|
| ES | INE FRONTUR, international tourist arrivals | `o + 1` |
| EL | Bank of Greece border survey, inbound non-resident travellers | `o` |
| IT | Banca d'Italia international tourism survey, foreign travellers | `o` |

Feature: year-on-year log growth at the information date. For each
country, two regressions per horizon on that country's rows only: WG's
regressors, and WG's regressors plus the national feature. Report the MASE
ratio at `h ≤ 3` on development and holdout. The series are retrieved,
frozen and committed before this part is run.
