# Gate 2 forecast backtest: development

Target months 2023-07 .. 2025-06, horizons 1-12.

## All models, common sample

| model | mean MASE | median rel. to SN | countries ≤ 0.90×SN | mean APE | 80% coverage |
|---|---|---|---|---|---|
| SN | 1.129 | 1.000 | 0/30 | 6.35% | n/a |
| SNG | 1.350 | 1.253 | 4/30 | 7.51% | n/a |
| AIRLINE | 1.204 | 1.086 | 10/30 | 6.40% | 90% |
| POOL_GR | 1.068 | 0.942 | 13/30 | 5.85% | 72% |
| CHRONOS | 1.595 | 1.452 | 4/30 | 8.24% | 95% |
| COMBO | 0.998 | 0.885 | 17/30 | 5.55% | 95% |
| POOL_GR_W | 1.036 | 0.910 | 13/30 | 5.70% | 71% |
| POOL_GR_WG | 1.026 | 0.906 | 15/30 | 5.70% | 71% |

Mean absolute percentage error by horizon:

| h | SN | SNG | AIRLINE | POOL_GR | CHRONOS | COMBO | POOL_GR_W | POOL_GR_WG |
|---|---|---|---|---|---|---|---|---|
| 1 | 6.14% | 5.50% | 5.18% | 5.21% | 7.78% | 4.97% | 5.22% | 5.19% |
| 2 | 6.13% | 6.09% | 5.87% | 5.44% | 8.02% | 5.32% | 5.43% | 5.41% |
| 3 | 6.14% | 6.69% | 6.46% | 5.70% | 8.53% | 5.66% | 5.64% | 5.60% |
| 4 | 6.13% | 7.71% | 6.88% | 6.09% | 8.68% | 5.77% | 5.87% | 5.61% |
| 5 | 6.24% | 7.80% | 6.73% | 6.01% | 8.31% | 5.45% | 5.76% | 5.52% |
| 6 | 6.37% | 7.69% | 6.89% | 5.91% | 8.16% | 5.63% | 5.66% | 5.53% |
| 7 | 6.40% | 8.08% | 6.98% | 6.04% | 8.63% | 5.74% | 5.81% | 5.71% |
| 8 | 6.50% | 7.87% | 6.62% | 5.92% | 8.31% | 5.56% | 5.76% | 5.76% |
| 9 | 6.53% | 8.06% | 6.78% | 5.96% | 8.44% | 5.84% | 5.77% | 5.88% |
| 10 | 6.51% | 8.50% | 6.25% | 5.98% | 7.96% | 5.49% | 5.86% | 6.18% |
| 11 | 6.65% | 8.39% | 5.98% | 6.02% | 7.93% | 5.52% | 5.83% | 6.16% |
| 12 | 6.72% | 9.06% | 6.26% | 6.14% | 8.06% | 5.86% | 6.02% | 6.31% |

Common sample: 7153 (country, target, horizon) cells.

## Selection (pre-registered rule: lowest mean MASE across countries)

Official-data candidates, on their common sample: SNG 1.350, AIRLINE 1.204, POOL_GR 1.068, CHRONOS 1.595, COMBO 0.998

- BEST_OFF: **COMBO**

Attention candidates, on their common sample: POOL_GR_W 1.036, POOL_GR_WG 1.026

- BEST_ALT: **POOL_GR_WG**
