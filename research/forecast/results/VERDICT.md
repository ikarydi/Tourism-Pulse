# Gate 2 verdict: attention helps forecasts 4–12 months ahead; no claim of beating last year's value

Holdout run once on 2026-09-27, after `SELECTION.md` was committed.
Targets 2025-07 .. 2026-06, horizons 1–12, 30 countries. Full tables are
in `holdout.md`.

## Gate

| criterion | result | verdict |
|---|---|---|
| G2-A skill: BEST_OFF (COMBO) MASE ≤ 0.90 × SN in ≥ 16/30 | 5/30 | **FAIL** |
| G2-B attention: POOL_GR_WG beats POOL_GR in ≥ 16/30, median ratio ≤ 0.97 | 26/30, 0.936 | **PASS** |
| Shipped model (attention model must also beat BEST_OFF) | POOL_GR_WG 0.930 vs COMBO 1.032 mean MASE | **POOL_GR_WG** |
| G2-C calibration: shipped model's 80% intervals cover 70–90% | 81% | **PASS** |

## What it means

1. **Attention is a leading indicator, not a coincident one.** Adding
   Wikipedia and GDELT to the same regression lowers error in 26 of 30
   countries (24 of 30 on development, same median ratio 0.936). The gain
   is concentrated at 4–12 months ahead:

   | h | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|
   | error reduction from attention | 0% | 1% | 0% | 3% | 4% | 4% | 4% | 4% | 3% | 5% | 4% | 4% |

   This fits Gate 1: attention barely helps for the current month, but it
   carries information about travel several months out, which is when
   people research trips.

2. **Last year's value is a strong benchmark.** The shipped model is
   better than seasonal naive in 20 of 30 countries, with a median error
   ratio of 0.931, 4.96% against 5.35% mean absolute percentage error. The
   gain is largest at short horizons (15% at h = 1) and small at 12 months
   (3%). It clears the pre-registered 10% bar in only 11 countries, so the
   product does **not** claim to beat last year's figure. Per the
   pre-registration, forecasts are published as a seasonal outlook with
   intervals, and accuracy claims wait for the live track record.

3. **The selected official model did worse on the holdout than on
   development.** COMBO was best on development (0.998 mean MASE) but
   worse than seasonal naive on the holdout (1.032), dragged down by
   CHRONOS and AIRLINE. The simpler pooled regression held up.

4. **The zero-shot foundation model is not a good baseline here.**
   CHRONOS loses to SARIMA in 26 of 30 countries (median ratio 1.44). On
   short series broken by COVID, it extrapolates the collapse and the
   rebound as if they were part of the pattern. This answers the plan's
   research question 2 for national monthly nights: classical models
   with an explicit COVID treatment win.

## Caveats

- **Same months as Gate 1's holdout.** Gate 1 had already scored nowcasts
  of these months. The forecasting models and horizons 4–12 are new, but
  the live record that starts now is the clean test.
- **The pre-registered Diebold–Mariano tests are degenerate on the
  holdout.** With 12 target months per country and lag 12, the
  small-sample correction factor is zero, so every p-value is 1. This
  says nothing about significance either way. As a post-hoc
  substitute across countries (countries are correlated, so this
  overstates certainty), a two-sided sign test gives:
  - attention vs none: 26/30, p = 0.0001
  - shipped model vs seasonal naive: 20/30, p = 0.10
  - CHRONOS vs SARIMA: 4/30, p = 0.0001
- **Country level only.** Regional series start in 2020 and are not
  validated. Regional forecasts use the same model and are labelled as
  having no track record yet.

## Product decision (as pre-registered)

- Ship POOL_GR_WG: direct pooled regressions per horizon on recent
  official growth plus Wikipedia and GDELT growth, with 80% intervals from
  residual quantiles.
- Publish it as a seasonal outlook, not as "beats last year".
- Store every forecast with its issue date, and score it when Eurostat
  publishes the month.
