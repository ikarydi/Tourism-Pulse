# Regional nowcast backtest (Hungary): dev

Target months 2023-10 .. 2025-07, horizons (1, 2).

## MASE by model (common sample, all areas)

| model | median MASE | median rel. to SN | areas ≤ 0.90×SN | mean APE | 80% coverage |
|---|---|---|---|---|---|
| SN | 1.013 | 1.000 | 0/12 | 8.8% | n/a |
| SNG | 1.153 | 1.129 | 1/12 | 8.9% | n/a |
| AIRLINE | 0.958 | 1.002 | 3/12 | 8.1% | 75% |
| POOL_GR | 1.098 | 1.091 | 2/12 | 8.6% | 67% |
| POOL_W | 1.091 | 1.080 | 2/12 | 8.7% | 66% |
| POOL_WG | 1.107 | 1.105 | 2/12 | 8.8% | 65% |

## Median relative MASE vs SN, by horizon

| h | SN | SNG | AIRLINE | POOL_GR | POOL_W | POOL_WG |
|---|---|---|---|---|---|---|
| 1 | 1.000 | 1.104 | 0.998 | 1.061 | 1.062 | 1.078 |
| 2 | 1.000 | 1.153 | 0.976 | 1.086 | 1.118 | 1.136 |

## Selection (pre-registered rule)

- Primary alt-data model: **POOL_W** (median rel. MASE 1.080)
- Best official-data-only baseline: **AIRLINE** (median rel. MASE 1.002)

## Per-area MASE (common sample)

| geo | SN | SNG | AIRLINE | POOL_GR | POOL_W | POOL_WG |
|---|---|---|---|---|---|---|
| balaton | 0.997 | 1.188 | 1.291 | 1.134 | 1.222 | 1.271 |
| budapest | 0.882 | 0.360 | 0.347 | 0.327 | 0.338 | 0.352 |
| buk_sarvar | 0.774 | 1.013 | 0.957 | 0.975 | 1.002 | 1.002 |
| debrecen | 0.977 | 1.198 | 1.174 | 1.110 | 1.212 | 1.256 |
| eger | 1.158 | 1.280 | 1.279 | 1.307 | 1.321 | 1.332 |
| greater_budapest | 1.233 | 1.379 | 1.246 | 1.354 | 1.412 | 1.432 |
| gyor_pannonhalma | 1.030 | 1.105 | 0.959 | 1.085 | 1.100 | 1.127 |
| gyula | 1.117 | 1.273 | 0.942 | 1.199 | 1.131 | 1.130 |
| pecs | 0.708 | 0.750 | 0.731 | 0.682 | 0.713 | 0.716 |
| sopron | 0.975 | 1.117 | 0.969 | 1.057 | 1.065 | 1.087 |
| szeged | 1.068 | 1.011 | 0.863 | 0.944 | 0.943 | 0.934 |
| tokaj_nyiregyhaza | 1.041 | 1.253 | 0.938 | 1.150 | 1.082 | 1.076 |
