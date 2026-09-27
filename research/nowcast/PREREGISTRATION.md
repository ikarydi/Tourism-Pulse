# Gate 1 nowcast backtest: pre-registration

Written and committed **before** any model was run on real data. The git
commit timestamp of this file is the evidence. Anything decided after
seeing results is marked as such in `results/`.

## Question

Do free, high-frequency open signals (Wikipedia pageviews, GDELT news)
improve nowcasts of official monthly tourism nights over statistical
baselines that use official data alone?

## Target and information set

- Target: Eurostat `tour_occ_nim`, nights spent, residents + non-residents,
  NACE I551-I553, 30 countries (EU27 + NO, IS, CH).
- Official data is published with a ~3-month lag (at end of September
  2026 most countries had data through June). So at origin `o` (the
  last published month) we nowcast `o+1`, `o+2`, `o+3` (horizons
  h = 1, 2, 3). h = 3 is the current month.
- Alt data is assumed known through `o+3` (complete months only).
- Eurostat values are the latest vintage (revisions ignored; applies to
  every model equally).

## Models

All regressions work on year-over-year log growth `d(t) = log x(t) - log x(t-12)`.
`dbar_y(o)` is the mean of `d_y` over `o-2..o`. For a signal `s`,
the "surprise" is `Δs(t) = d_s(t) - dbar_s(o)`.

| id | forecast of y(t), t = o+h |
|---|---|
| SN | y(t-12) |
| SNG | y(t-12) · exp(dbar_y(o)) |
| AIRLINE | SARIMA(0,1,1)(0,1,1)12 on log y, COVID months set missing |
| GR | per-country OLS: d_y(t) = a + b·dbar_y(o) |
| GR_W | GR + c·Δwiki(t) |
| GR_WG | GR_W + g·Δgdelt_share(t) + k·Δtone(t) |
| POOL_W | GR_W with slopes and intercept pooled across countries |
| POOL_WG | GR_WG pooled across countries |

- `wiki` = sum of en country + de country + en capital article views.
- `gdelt_share` = monthly GDELT article count for "<country> tourism" ÷
  GDELT corpus total; `tone` = article-weighted mean tone (difference,
  not log).
- Regression training samples: every target month `t <= o` with complete
  features, excluding any sample where `t`, `o-2..o`, or any of those
  minus 12 months falls in 2020-03 .. 2021-12 (COVID).
- h is a separate regression per horizon (direct forecasting).

## Periods

- **Development** targets: 2023-07 .. 2025-06. Used to choose the one
  primary alt-data model.
- **Holdout** targets: 2025-07 .. 2026-06 (or the latest official month).
  Run once, after the primary model is fixed and committed.

## Metrics

- MASE with a fixed per-country scale: mean |y(t) - y(t-12)| over
  2016-01 .. 2019-12. Averaged over h = 1..3 and all target months.
- Relative MASE = model MASE / SN MASE, per country.
- 80% interval coverage (regressions: empirical residual quantiles;
  AIRLINE: model interval).
- Diebold-Mariano test (Harvey-Leybourne-Newbold correction) per country
  on h-averaged absolute errors, primary vs SN and primary vs best
  official-data-only baseline.

## Primary model selection (on development only)

Among GR_W, GR_WG, POOL_W, POOL_WG: the lowest **median relative MASE**
across countries on the development period.

## Gate (as stated in the Pulse to Product report)

**Pass** if the primary model's relative MASE vs SN is ≤ 0.90 in a
majority of countries (≥ 16 of 30) on the holdout.

## Stricter scientific check (reported, not gating)

Does the primary model beat the best official-data-only baseline
(SNG, AIRLINE, GR, chosen on development) in a majority of countries on
the holdout? If the gate passes but this fails, the alt-data signals are
not the reason, and the product claim must say so.

## Amendment 1 (2026-09-27, before any GDELT-based result was produced)

**Change:** the GDELT inputs now come from GDELT's daily Global Knowledge
Graph files (`data.gdeltproject.org/gkg/YYYYMMDD.gkg.csv.zip`) instead
of the DOC 2.0 API.

**Why:** the DOC API throttled this machine to roughly one request per
5-15 minutes and then refused all requests for 5+ minutes at a time,
making the 60-request backfill impractical. The raw files are served
from static storage without throttling.

**New definitions** (per country, per month):

- An article record counts as *tourism* if its THEMES contain any of
  `TOURISM`, `WB_825_TOURISM`, `TAX_FNCACT_TOURIST`, `TAX_FNCACT_TOURISTS`.
- It counts for a country if any of its LOCATIONS carries that country's
  FIPS code (one count per record per country).
- `articles` = sum of NUMARTS over tourism records mentioning the
  country; `corpus` = sum of NUMARTS over all records that day. So
  `gdelt_share` = articles / corpus, as before.
- `tone` = NUMARTS-weighted mean of the first TONE field over the same
  records.
- Monthly values sum or average over the days available (missing daily
  files are skipped and counted).

Models, periods, metrics, selection rule and gate are unchanged. At the
time of this amendment only the models without GDELT had been run
(development period, pipeline check); no model using GDELT had produced
any number.

## Amendment 2 (2026-09-27, before any GDELT-based result was produced)

**Change:** GDELT data (Amendment 1 definitions) covers 2022-01 onward
instead of 2017-01 onward.

**Why:** the daily files total ~115 GB and download at ~13 MB/s here,
about 2 h 10 min for the full span; from 2022-01 it is ~47 GB, about
1 h. Decided by the project owner to shorten the wait.

**Consequences, stated in advance:**

- GDELT months in 2020-2021 were already useless: every sample using
  them falls under the COVID exclusion. The real loss is the pre-COVID
  training history (targets 2018-04 .. 2020-02) for GR_WG and POOL_WG.
- With no pre-COVID samples, GR_WG (per country, needs ≥ 12 training
  samples) first forecasts around mid-2024. Because comparisons use the
  common sample of all models, the development comparison effectively
  covers about 2024-06 .. 2025-06 instead of 2023-07 .. 2025-06.
- Wikipedia models keep their 2016+ history, so the development
  selection slightly favours them over the GDELT models.
- On the holdout every GDELT model has 20+ training months per country;
  the gate test is essentially unaffected.

Models, periods, metrics, selection rule and gate are otherwise
unchanged. A later robustness check may backfill 2017-2021.
