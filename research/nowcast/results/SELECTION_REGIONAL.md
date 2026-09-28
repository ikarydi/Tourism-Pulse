# Gate 1b selection (from regional_dev, committed before the holdout run)

- **Primary alt-data model: POOL_W** (median relative MASE vs SN 1.080;
  POOL_WG 1.105). Both alt-data models are worse than seasonal naive at
  the median area on dev.
- **Best official-data-only baseline: AIRLINE** (1.002).
- Budapest is the exception on dev: all growth models ~0.33-0.36 MASE
  vs SN 0.88.
- GDELT attention for Eger, Pécs and Bük-Sárvár is ~0 mentions/month
  (median); verified against a raw 2025 GKG file that this is real
  coverage, not a matching error.

    python -m research.nowcast.regional --period holdout --primary POOL_W --baseline AIRLINE
