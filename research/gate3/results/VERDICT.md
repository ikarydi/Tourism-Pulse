# Gate 3 verdict: flights and the hotel survey do not improve forecasts 1–3 months ahead

Holdout run once on 2026-09-28, after `SELECTION.md` was committed.
Targets 2025-07 .. 2026-06; decisions on horizons 1–3. Full tables are in
`holdout.md`; Part 2 is in `national.md`.

## Gate

| criterion | result | verdict |
|---|---|---|
| G3-A flights: WG_F beats WG in a majority of eligible countries, median MASE ratio ≤ 0.97 | 16/30, 0.996 | **FAIL** |
| G3-B survey: WG_S beats WG in a majority, median ≤ 0.97 | 6/25, 1.019 | **FAIL** |
| Shipped model at h ≤ 3 (BEST_T = WG_S if its source passed, else a passing source, else WG) | | **WG, unchanged** |
| G3-C calibration of the shipped model | WG covers 82% at h ≤ 3 | not applicable (nothing new ships) |

The baseline WG is Gate 2's shipped model, POOL_GR_WG, reproduced exactly
(the same 7,153 development forecasts).

## What it means

1. **Earlier official data adds nothing the model does not already know.**
   Flight growth for the month after the origin beat the baseline in 16 of
   30 countries, a coin toss (sign test p = 0.86), with a median error
   ratio of 0.996. On development it was 13 of 27 and 1.002. The model
   already carries recent growth in nights and attention; year-on-year
   growth in aircraft movements at the country's airports tells it little
   more. Flights count aircraft, not passengers, and include residents
   flying out and business and cargo flights.

2. **The hotel survey made forecasts worse.** Adding the change in hotels'
   expected-demand balance raised error in 19 of 25 countries (sign test
   p = 0.015, median ratio 1.019), and on development in 14 of 22. Using the
   survey a month earlier (WG_S2, its usual availability) was no better
   (6/25, 1.021). Hotels' three-month expectations do not translate into
   nights growth at the national level.

3. **Nothing changes further out.** At horizons 4–12 neither source helps
   (flights 13/30 better, median 1.004; survey 7/24, 1.014). Gate 2's
   finding stands: attention is what helps there.

4. **Flights do not stand in for attention.** GR_F (recent nights growth
   plus flights, without Wikipedia or GDELT) beat WG in 18 of 30 countries on
   the holdout (median 0.986) but lost in 20 of 27 on development (1.029).
   The two periods disagree, so this supports no claim either way.

5. **Part 2, Spain (descriptive).** FRONTUR, published about a month after
   the month ends, helped a Spain-only regression on development (MASE ratio
   0.968 at h ≤ 3) and hurt it on the holdout (1.280, on 36 cells where both
   models were already within about 2%). No reliable gain. Greece's and
   Italy's series could not be retrieved (`data/NATIONAL.md`), so Part 2 has
   one country.

## Caveats

- **Same holdout months as Gates 1 and 2.** The baseline's errors on them
  were known; the new regressors had never been evaluated. The result is a
  clear miss, not a near miss, so the reuse is unlikely to have changed it.
- **Final data, not real-time vintages.** Flights, the survey and nights are
  all as published now. Revisions to nights would, if anything, favour the
  timely sources in a real-time test, since they were published before the
  revisions; this is not tested here.
- **Information date.** Both sources were used at o + 1, the date they are
  reliably out when Eurostat publishes month o. The survey at o + 2 was
  tested descriptively and did not help.
- **Country level only.** Flights may matter more for island and airport
  regions (the South Aegean, the Balearics) than for countries; regional
  nights series start in 2020, too short for a clean test yet.

## Product decision (as pre-registered)

- The outlook keeps Gate 2's model at every horizon. No shadow model is
  needed, as nothing new ships.
- Flights, the hotel survey, prices, turnover and origin markets stay in the
  app as context beside the outlook ("Inbound travel & economy"), with no
  claim that they improve forecasts.

## For the research agenda

Four pre-registered studies now point the same way: at short horizons, a
pooled regression on official nights growth is hard to beat, whether with
open attention data (Gates 1 and 1b) or with earlier official indicators
(Gate 3). Attention earns its place only 4–12 months out (Gate 2). That
pattern, with the failed gates reported in full, is the paper.
