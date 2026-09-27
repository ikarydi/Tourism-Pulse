# Gate 2: forecasting official tourism nights 1–12 months ahead

Pre-registered on 2026-09-27, before any Gate 2 forecast was computed.
Follows Gate 1 (`research/nowcast/`), which found that Wikipedia and GDELT
add only ~3% over official data when nowcasting the current month.

## Question

The product plan ("Pulse to Product", 90-day plan) lists forecasting as
the missing layer and a public, time-stamped track record as the main
defence. Gate 2 asks three things:

1. **Skill.** Does the best official-data model forecast monthly nights
   1–12 months ahead clearly better than last year's value?
2. **Attention.** Do Wikipedia and GDELT improve those forecasts over the
   same model without them? Gate 1 saw the edge grow with horizon; this
   is where a longer lead could matter.
3. **Foundation model** (research question, not a gate). How does a
   zero-shot time-series foundation model (Chronos-Bolt) compare with
   classical models on short, seasonal, COVID-broken tourism series?

## Data (fixed)

The Gate 1 snapshots in `research/nowcast/data/`, retrieved 2026-09-27:

- `nights.csv`: Eurostat `tour_occ_nim`, nights spent, all accommodation,
  30 countries (EU27 + CH, IS, NO), monthly, 2014-01 to 2026-06/07.
- `pageviews.csv`: Wikipedia monthly user views, three series per country
  (as Gate 1: a month counts only when all three report it).
- `gdelt_full.csv`: GDELT tourism-article share and tone per country,
  2017-01 to 2020-02 and 2022-01 onward.

No other data is added after this file is committed.

## Set-up

- **Origin** `o`: the last month with an official figure. **Target**
  `t = o + h`, horizons `h = 1 … 12`.
- **Information at the origin**: official nights up to `o`; Wikipedia and
  GDELT up to `a = o + 1` (national figures are published 6–10 weeks after
  the month, by when the following month's attention data are complete).
- **COVID**: months 2020-03 to 2021-12 are missing for SARIMA, and any
  regression row whose target, base year or feature months (or their
  year-earlier months) fall in that span is left out of training and
  evaluation, as in Gate 1.
- Everything is forecast in logs and reported in nights.

## Models

Official data only:

| Name | Definition |
|---|---|
| SN | Seasonal naive: `y[t-12]`. The benchmark. |
| SNG | `y[t-12] × exp(ḡ_o)`, where `ḡ_o` is the mean year-on-year log growth over `o-2 … o`. |
| AIRLINE | SARIMA(0,1,1)(0,1,1)12 on log nights, refitted at every origin. |
| POOL_GR | Direct pooled regression per horizon: `log(y_t / y_{t-12}) = α_h + β_h ḡ_o`, fitted on all countries' rows with target ≤ `o`. |
| CHRONOS | Chronos-Bolt (small), zero-shot, on log nights up to `o` (COVID months as missing). Median and 10%/90% quantiles. |
| COMBO | Equal-weight mean of the log forecasts of AIRLINE, POOL_GR and CHRONOS. |

With attention (both extend POOL_GR):

| Name | Extra regressors, measured over `a-2 … a` |
|---|---|
| POOL_GR_W | mean year-on-year log growth of Wikipedia views |
| POOL_GR_WG | the same, plus GDELT tourism share growth and tone change |

80% intervals: SARIMA's own; regressions use the 10% and 90% quantiles of
their training residuals (as Gate 1); CHRONOS its own quantiles; COMBO the
mean of the members' log bounds.

## Periods

- **Development**: targets 2023-07 to 2025-06, every horizon.
- **Holdout**: targets 2025-07 to 2026-06, every horizon. Run once, after
  the selection below is committed.

The holdout months are Gate 1's holdout months. Gate 1 only looked at
nowcasts (h ≤ 3) of them, but it did show that alternative data added
little, which is prior knowledge for question 2. The clean test of
whatever ships is the live track record that starts with this gate.

## Scoring

- MASE per country: absolute error divided by the mean absolute
  seasonal difference over 2016-01 to 2019-12 (as Gate 1), averaged over
  all (target, horizon) cells.
- Any comparison of two models uses only the cells both forecast.
- 80% interval coverage, pooled over countries and horizons.
- MAPE by horizon (descriptive). Diebold–Mariano tests (HLN correction,
  lag 12) per country on absolute scaled errors (descriptive).

## Selection on development (committed before the holdout)

- **BEST_OFF**: of SNG, AIRLINE, POOL_GR, CHRONOS and COMBO, the lowest
  mean MASE across countries.
- **BEST_ALT**: of POOL_GR_W and POOL_GR_WG, the lowest mean MASE.

## Gate criteria (holdout)

- **G2-A skill: pass** if BEST_OFF has MASE ≤ 0.90 × SN in at least
  16 of 30 countries.
- **G2-B attention: pass** if BEST_ALT beats POOL_GR (MASE ratio < 1) in at
  least 16 of 30 countries **and** the median ratio is ≤ 0.97.
- **G2-C calibration: pass** if the 80% intervals of the model that ships
  cover between 70% and 90% of holdout outcomes.

## What each outcome means for the product

- G2-A pass: publish forecasts with the claim that they beat last year's
  value, backed by these numbers. G2-A fail: publish forecasts only as a
  seasonal outlook, without an accuracy claim beyond the live record.
- G2-B pass **and** BEST_ALT also has a lower holdout MASE than BEST_OFF:
  the shipped model uses attention. Otherwise the shipped model is
  BEST_OFF, and Wikipedia and GDELT stay an insight layer beside it.
- G2-C fail: before publishing, widen (or narrow) the intervals by the
  factor that gives 80% coverage on the development period
  (split-conformal on log errors), and report that this was needed.
- In every case, forecasts are stored with their issue date and scored
  when Eurostat publishes the month. Per the plan's kill criteria, if the
  live record after six months is clearly worse than this backtest, the
  method is fixed before any accuracy is advertised.
