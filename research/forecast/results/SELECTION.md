# Gate 2 selection (development period)

Committed before the holdout was run. Rule and candidates as in
`PREREGISTRATION.md`; numbers from `dev.md` (targets 2023-07 .. 2025-06,
horizons 1-12).

- **BEST_OFF = COMBO** (mean MASE 0.998 on the official candidates' common
  sample; POOL_GR 1.068, AIRLINE 1.204, SNG 1.350, CHRONOS 1.595).
- **BEST_ALT = POOL_GR_WG** (1.026; POOL_GR_W 1.036).

Holdout command:

    python -m research.forecast.backtest --period holdout --best-off COMBO --best-alt POOL_GR_WG

Observations from development, recorded before the holdout:

- CHRONOS on its own is worse than seasonal naive here (8.2% mean APE
  against 6.4%), probably because the zero-shot model reads the COVID gap
  and the rebound as part of the series. It still helps COMBO.
- Adding attention to POOL_GR lowers development MASE by about 4%
  (1.068 to 1.026), in line with Gate 1's small edge.
- AIRLINE's 80% intervals cover 90% and the regressions' 71-72%: COMBO
  (95%) is too wide on development, so G2-C may need the pre-registered
  recalibration.
