# Gate 3 selection (development period)

Committed before the holdout was run. Rule and candidates as in
`PREREGISTRATION.md`; numbers from `dev.md` (targets 2023-07 .. 2025-06,
decisions on horizons 1-3).

- **BEST_T = WG_S** (mean MASE at h ≤ 3 on the three candidates' common
  sample: WG_S 0.941, WG_F 0.942, WG_FS 0.944). The margin is 0.001, so the
  choice between the candidates carries almost no information.

Holdout command:

    python -m research.gate3.backtest --period holdout --best-t WG_S

The baseline WG reproduces Gate 2's POOL_GR_WG exactly on development (the
same 7,153 forecasts, zero difference), so the comparison is against the
model that ships today.

Observations from development, recorded before the holdout:

- **Neither source clears the gate's bar on development.** WG_F beats WG in
  13 of 27 countries (median MASE ratio 1.002), WG_S in 8 of 22 (1.006). The
  holdout would need a clearly different picture for either gate to pass.
- The small gains that exist sit at h = 1-2 (MAPE −0.5% to −1.9% relative to
  WG) and vanish at h = 3.
- **Flights do not stand in for attention.** GR_F (flights, no Wikipedia or
  GDELT) is worse than WG in 20 of 27 countries at h ≤ 3 (median 1.029).
- **The survey's extra month does not help.** WG_S2 (survey at o + 2) is
  identical to WG_S at h ≤ 3 (8/22, 1.006).
- Adding either source to WG does not change interval coverage at h ≤ 3
  (72%, WG_S2 71%).
