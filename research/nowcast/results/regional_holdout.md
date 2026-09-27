# Regional nowcast backtest (Hungary): holdout

Target months 2025-08 .. 2026-07, horizons (1, 2).

## MASE by model (common sample, all areas)

| model | median MASE | median rel. to SN | areas ≤ 0.90×SN | mean APE | 80% coverage |
|---|---|---|---|---|---|
| SN | 0.647 | 1.000 | 0/12 | 5.3% | n/a |
| SNG | 0.662 | 1.065 | 3/12 | 5.3% | n/a |
| AIRLINE | 0.736 | 1.257 | 3/12 | 5.9% | 85% |
| POOL_GR | 0.566 | 0.913 | 6/12 | 4.9% | 93% |
| POOL_W | 0.585 | 0.945 | 5/12 | 5.0% | 92% |
| POOL_WG | 0.582 | 0.948 | 5/12 | 5.0% | 92% |

## Median relative MASE vs SN, by horizon

| h | SN | SNG | AIRLINE | POOL_GR | POOL_W | POOL_WG |
|---|---|---|---|---|---|---|
| 1 | 1.000 | 0.961 | 1.230 | 0.891 | 0.973 | 0.958 |
| 2 | 1.000 | 1.076 | 1.258 | 0.951 | 0.937 | 0.948 |

## Gate: POOL_W vs SN and vs AIRLINE

- Areas with rel. MASE vs SN ≤ 0.90: **5/12** (pass needs ≥ 7) → **FAIL**
- Areas beating AIRLINE: **10/12** → stricter check **PASS**
- DM p < 0.10 better than SN: 0; better than AIRLINE: 1

| geo | rel. vs SN | rel. vs AIRLINE | DM p vs SN | DM p vs AIRLINE |
|---|---|---|---|---|
| balaton | 1.262 | 0.695 | 0.390 | 0.409 |
| budapest | 0.780 | 0.964 | 0.461 | 0.885 |
| buk_sarvar | 0.947 | 0.588 | 0.861 | 0.256 |
| debrecen | 1.296 | 0.909 | 0.136 | 0.629 |
| eger | 0.813 | 0.589 | 0.291 | 0.025 |
| greater_budapest | 0.795 | 0.995 | 0.594 | 0.984 |
| gyor_pannonhalma | 0.738 | 0.717 | 0.494 | 0.418 |
| gyula | 1.281 | 1.118 | 0.267 | 0.631 |
| pecs | 0.894 | 0.862 | 0.600 | 0.205 |
| sopron | 1.123 | 0.820 | 0.449 | 0.192 |
| szeged | 0.943 | 1.061 | 0.848 | 0.428 |
| tokaj_nyiregyhaza | 1.115 | 0.628 | 0.413 | 0.125 |

## Per-area MASE (common sample)

| geo | SN | SNG | AIRLINE | POOL_GR | POOL_W | POOL_WG |
|---|---|---|---|---|---|---|
| balaton | 0.656 | 0.839 | 1.192 | 0.870 | 0.828 | 0.806 |
| budapest | 0.620 | 0.511 | 0.501 | 0.485 | 0.483 | 0.485 |
| buk_sarvar | 0.271 | 0.279 | 0.436 | 0.251 | 0.256 | 0.262 |
| debrecen | 0.333 | 0.445 | 0.476 | 0.410 | 0.432 | 0.434 |
| eger | 0.738 | 0.691 | 1.019 | 0.570 | 0.600 | 0.595 |
| greater_budapest | 0.910 | 0.795 | 0.728 | 0.683 | 0.724 | 0.715 |
| gyor_pannonhalma | 0.708 | 0.554 | 0.729 | 0.494 | 0.523 | 0.509 |
| gyula | 0.738 | 0.888 | 0.845 | 0.830 | 0.945 | 0.970 |
| pecs | 0.638 | 0.633 | 0.661 | 0.561 | 0.570 | 0.570 |
| sopron | 0.623 | 0.765 | 0.853 | 0.662 | 0.700 | 0.707 |
| szeged | 0.969 | 1.066 | 0.861 | 0.870 | 0.914 | 0.901 |
| tokaj_nyiregyhaza | 0.418 | 0.498 | 0.743 | 0.460 | 0.466 | 0.467 |
