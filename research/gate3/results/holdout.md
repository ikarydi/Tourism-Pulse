# Gate 3 backtest: holdout

Target months 2025-07 .. 2026-06, horizons 1-12; decisions use h ≤ 3. Selected on development: BEST_T = WG_S.

## Gate

- **G3-A flights**: WG_F beats WG in **16/30** eligible countries, median MASE ratio **0.996** (needs ≥ 16 and ≤ 0.97), sign test p = 0.856 → **FAIL**
- **G3-B survey**: WG_S beats WG in **6/25** eligible countries, median MASE ratio **1.019** (needs ≥ 13 and ≤ 0.97), sign test p = 0.015 → **FAIL**
- Shipped model at h ≤ 3 (rule: BEST_T if all its sources passed, else the single passing source, else WG): **WG**
- **G3-C calibration**: WG 80% intervals cover **82%** of eligible holdout outcomes at h ≤ 3 (needs 70-90%) (WG stays; for reference)

## h ≤ 3, each model against WG

| model vs WG | countries better | median MASE ratio | sign test p | model MAPE | WG MAPE | model 80% coverage |
|---|---|---|---|---|---|---|
| WG_F | 16/30 | 0.996 | 0.856 | 4.73% | 4.72% | 80% |
| WG_S | 6/25 | 1.019 | 0.015 | 4.83% | 4.77% | 80% |
| WG_FS | 11/25 | 1.005 | 0.690 | 4.80% | 4.77% | 79% |
| WG_S2 | 6/25 | 1.021 | 0.015 | 4.88% | 4.81% | 79% |
| GR_F | 18/30 | 0.986 | 0.362 | 4.67% | 4.72% | 81% |

## h = 4-12 (descriptive)

| model vs WG | countries better | median MASE ratio | sign test p | model MAPE | WG MAPE | model 80% coverage |
|---|---|---|---|---|---|---|
| WG_F | 13/30 | 1.004 | 0.585 | 5.00% | 5.02% | 81% |
| WG_S | 7/24 | 1.014 | 0.064 | 4.76% | 4.72% | 81% |
| WG_FS | 10/24 | 1.010 | 0.541 | 4.72% | 4.72% | 82% |
| WG_S2 | 8/24 | 1.016 | 0.152 | 4.76% | 4.72% | 81% |
| GR_F | 12/30 | 1.012 | 0.362 | 5.01% | 5.02% | 80% |

Mean absolute percentage error by horizon, SN and WG on WG's cells:

| h | SN | WG |
|---|---|---|
| 1 | 5.33% | 4.51% |
| 2 | 5.33% | 4.72% |
| 3 | 5.33% | 4.94% |
| 4 | 5.33% | 4.90% |
| 5 | 5.34% | 4.92% |
| 6 | 5.36% | 4.96% |
| 7 | 5.38% | 5.02% |
| 8 | 5.38% | 5.02% |
| 9 | 5.36% | 5.12% |
| 10 | 5.34% | 5.13% |
| 11 | 5.34% | 5.10% |
| 12 | 5.35% | 5.19% |

Each model's MAPE relative to WG's on the cells both forecast (negative = more accurate):

| h | WG_F | WG_S | WG_FS | WG_S2 | GR_F |
|---|---|---|---|---|---|
| 1 | -0.6% | +1.7% | +0.4% | +1.7% | -1.5% |
| 2 | +0.0% | +0.8% | +0.3% | +1.3% | -1.6% |
| 3 | +0.9% | +1.7% | +1.4% | +1.0% | -0.7% |
| 4 | +0.9% | +1.5% | +1.5% | +1.6% | +1.5% |
| 5 | +0.6% | +1.7% | +1.7% | +1.7% | +1.6% |
| 6 | +0.5% | +2.3% | +2.2% | +2.3% | +1.2% |
| 7 | -0.1% | +2.2% | +1.7% | +1.9% | -0.4% |
| 8 | +0.0% | +1.1% | +0.6% | +1.5% | -0.2% |
| 9 | -0.6% | +0.3% | -0.5% | -0.1% | -1.8% |
| 10 | -2.0% | -0.7% | -2.7% | -0.7% | -0.4% |
| 11 | -1.2% | -0.8% | -2.3% | -1.1% | -0.9% |
| 12 | -1.9% | +0.2% | -2.4% | +0.6% | -1.6% |

## Per country, h ≤ 3 (MASE ratio to WG)

| geo | WG_F | WG_S | WG_FS |
|---|---|---|---|
| AT | 0.975 | 1.019 | 0.986 |
| BE | 1.030 | 1.055 | 1.049 |
| BG | 0.984 | 1.064 | 1.013 |
| CH | 1.008 | n/a | n/a |
| CY | 0.981 | 1.002 | 0.992 |
| CZ | 0.984 | 1.063 | 1.017 |
| DE | 1.010 | 1.056 | 1.033 |
| DK | 1.038 | 1.040 | 1.038 |
| EE | 0.936 | 1.022 | 0.941 |
| EL | 1.114 | 1.199 | 1.190 |
| ES | 1.029 | n/a | n/a |
| FI | 1.025 | 1.059 | 1.005 |
| FR | 0.954 | 1.028 | 0.959 |
| HR | 1.008 | 1.013 | 1.018 |
| HU | 0.959 | 1.004 | 0.962 |
| IE | 0.978 | 1.000 | 0.982 |
| IS | 0.979 | n/a | n/a |
| IT | 1.010 | 0.975 | 1.005 |
| LT | 0.976 | 0.992 | 0.970 |
| LU | 0.997 | n/a | n/a |
| LV | 1.013 | 1.063 | 1.013 |
| MT | 0.875 | 0.960 | 0.902 |
| NL | 0.986 | 1.007 | 0.989 |
| NO | 0.970 | n/a | n/a |
| PL | 0.995 | 0.957 | 0.963 |
| PT | 1.110 | 1.239 | 1.219 |
| RO | 1.083 | 1.014 | 1.084 |
| SE | 0.966 | 1.070 | 0.987 |
| SI | 1.019 | 1.014 | 1.015 |
| SK | 1.240 | 0.994 | 1.201 |
