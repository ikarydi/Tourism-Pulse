# Gate 1, phase 2 (robustness check): gate still FAILS; small consistent edge

Pre-COVID GDELT history restored (2017-01 .. 2020-02 plus 2022+).
Selection on dev: POOL_WG vs GR (`SELECTION_PHASE2.md`). Full numbers in
`holdout_phase2.md`. The holdout had already been seen in phase 1, so
this is a robustness check, not a fresh confirmatory test.

## Gate (vs seasonal naive)

POOL_WG ≤ 0.90 × SN MASE in **15 of 30** countries; needed ≥ 16.
**FAIL** (phase 1: 13/30). The official-data-only GR also reaches 15/30.

## Alternative data vs official data only (GR)

| | phase 1 (POOL_W) | phase 2 (POOL_WG) |
|---|---|---|
| countries better than GR | 17/30 | 20/30 |
| significantly better (DM p < 0.10) | 2 | 5 (DE, ES, IE, LV, PT) |
| significantly worse | 3 | 1 (RO) |
| median error ratio vs GR | 0.973 | 0.970 |

Mean absolute percentage error by horizon (phase 2 holdout):

| h | SN | GR | POOL_WG |
|---|---|---|---|
| 1 | 5.33% | 4.51% | 4.45% |
| 2 | 5.33% | 4.77% | 4.72% |
| 3 | 5.33% | 4.96% | 4.84% |

## Reading

- With a long enough GDELT history, Wikipedia + GDELT gives a small but
  mostly consistent improvement over official-data-only nowcasting,
  largest at the current-month horizon (h = 3).
- The size is small: ~3% lower error at the median country, ~0.1
  percentage points of MAPE. Most of the gain over seasonal naive comes
  from the statistical model on official data, not from alternative data.
- GDELT needs its pre-COVID training history: without it, per-country
  GDELT models overfit (phase 1).
- The gate verdict stands: FAIL at country level.
