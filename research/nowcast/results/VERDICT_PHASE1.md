# Gate 1, phase 1 verdict: FAIL

Holdout 2025-07 .. 2026-06, 30 countries, horizons 1-3, run once with the
primary model and baseline chosen on the development period
(`SELECTION.md`). Full numbers in `holdout.md`.

## Pre-registered gate

POOL_W (Wikipedia, pooled regression) scored ≤ 0.90 × seasonal-naive MASE
in **13 of 30** countries. The gate needed ≥ 16. **FAIL.** Median ratio
0.910.

## Stricter check (reported, not gating)

POOL_W beat the official-data-only growth regression (GR) in 17 of 30
countries, but Diebold-Mariano tests find it significantly better in
only 2 (DE, PT) and significantly worse in 3 (FI, RO, SE) at p < 0.10.
No reliable edge from the alternative data.

## What the holdout says

- The official-data-only regression GR clears the 10% bar in 15 of 30
  countries by itself; POOL_WG in 15, POOL_W in 13. **No model, with or
  without alternative data, reaches a majority.**
- All models sit at 4.7-5.4% mean absolute percentage error; seasonal
  naive is already a strong benchmark for national monthly nights.
- Per-country GDELT regressions (GR_WG) overfit badly with post-2022
  training history only (72% coverage on 80% intervals).
- 80% intervals are roughly calibrated on the holdout (80-87%) except
  GR_WG.

## Consequence for the product (from the Pulse to Product kill criteria)

At country level, "open signals predict official demand" is not
supported. The pre-stated pivot is the tourism-pressure observatory,
which needs no forecasting edge. A nowcast product could still offer
*timeliness* (GR-style statistical nowcasts ~3 months ahead of Eurostat)
but must not claim an alternative-data advantage.

Not tested here, and not a rescue of this result: whether alternative
data helps at city/regional level, where Wikipedia city articles and
GDELT locations are more specific. That needs its own pre-registered
study (e.g. KSH monthly regional nights for Hungary).

Phase 2 (pre-COVID GDELT history) follows as a robustness check; it
cannot overturn this verdict on its own.
