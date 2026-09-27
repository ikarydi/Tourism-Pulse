# Gate 1b (regional, Hungary) verdict: FAIL

Holdout 2025-08 .. 2026-07, 12 KSH tourism areas, horizons 1-2, run once
with the model and baseline chosen on dev (`SELECTION_REGIONAL.md`).
Full numbers in `regional_holdout.md`.

## Gate

POOL_W ≤ 0.90 × seasonal-naive MASE in **5 of 12** areas; needed ≥ 7.
**FAIL.** No area shows a significant improvement over SN (DM p < 0.10).

## Stricter check

POOL_W beats the pre-selected baseline (AIRLINE) in 10 of 12 areas, but
AIRLINE broke down on the holdout (1.257 × SN), so this says little.
Against the official-data-only pooled regression POOL_GR, which was not
the selected baseline but is the fair comparison, POOL_W is worse:
POOL_GR reaches 6/12 areas and a median 0.913 × SN vs POOL_W's 0.945.
POOL_WG (adding GDELT attention) is no better (0.948).

## Reading

- The hypothesis that sub-national signals are sharper and therefore
  more useful is not supported. Wikipedia and GDELT attention add no
  measurable nowcasting value for Hungarian tourism areas.
- GDELT's global corpus barely covers small Hungarian destinations
  (median 0 monthly mentions for Eger, Pécs, Bük-Sárvár).
- A pooled regression on official data alone is the best nowcaster at
  both levels tested (countries and Hungarian areas): roughly 5-10%
  lower error than last year's figure, delivered 2-3 months before the
  statistics office publishes.
- Intervals over-cover on the holdout (92-93% for a nominal 80%):
  conservative, which is acceptable for a product.

## Consequence

Across Gate 1 (countries, two phases) and Gate 1b (regions), the
alternative-data nowcasting claim fails. Nowcasting stays in the product
only as an official-data statistical estimate, sold on timeliness, not on
alternative data. The tourism-pressure observatory is the product focus.
