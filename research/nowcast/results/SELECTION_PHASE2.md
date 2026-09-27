# Phase 2 selection (from dev_phase2, committed before the phase 2 holdout run)

With GDELT history from 2017 (pre-COVID training samples restored):

- **Primary alt-data model: POOL_WG** (median relative MASE vs SN 0.891;
  16/30 countries ≤ 0.90 on dev). POOL_W 0.916, GR_W 0.911.
- **Best official-data-only baseline: GR** (0.940).
- GR_WG no longer overfits as badly (0.961 vs 1.075 in phase 1).
- Development comparison now covers all 30 countries.

Phase 2 is a robustness check on a holdout already seen in phase 1; it
cannot overturn the phase 1 FAIL on its own.

    python -m research.nowcast.backtest --period holdout --phase 2 --primary POOL_WG --baseline GR
