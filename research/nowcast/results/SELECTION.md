# Phase 1 selection (from dev, committed before the holdout run)

Applied the pre-registered rule to `dev.md`:

- **Primary alt-data model: POOL_W** (median relative MASE vs SN 0.898;
  runner-up POOL_WG 0.910). POOL_WG was better at h = 2 and 3, but the
  rule selects on the overall median and is not overridden.
- **Best official-data-only baseline: GR** (0.945).

Notes recorded before the holdout:

- Development comparison covered 28 countries. BG and EE dropped out:
  Eurostat withholds several of their off-season months (BG 25, EE 13
  missing months since 2014), so GR_WG never reached 12 clean training
  samples there.
- Gate counting follows PREREGISTRATION.md literally: pass needs ≥ 16 of
  the 30 countries. A country without holdout forecasts counts as not
  beating SN.

Holdout command, to be run once:

    python -m research.nowcast.backtest --period holdout --primary POOL_W --baseline GR
