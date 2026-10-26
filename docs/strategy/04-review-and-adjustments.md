# Review of the Budapest Market Brief plan, and adjustments

## Agree
- Sell before building; the pipeline already exists, demand does not.
- No forecast claims. Gate 1-3 do not support alternative-data accuracy; place-level forecasts are `validated: no`.
- Run locally and export PDF/spreadsheet; do not deploy the full platform for a pilot.

## Change
1. **Target customer vs evidence.** The cited statistic (51% of DMOs name data analysis a major challenge; 45% struggle to
   make it actionable; not independently verified here) is about destination marketing organizations, not small Budapest
   operators. Operators can get most raw data free (KSH, Budapest tourism office, Eurostat). Pilot first with consultants and
   one or two DMOs/districts at EUR 150-400 per report or retainer; test the EUR 29-59 tier with operators in parallel.
   At EUR 29/month, 50 customers is ~EUR 1,950 gross with a real support load.
2. **Month-1 target is optimistic.** 3-5 paid pilots from cold outreach in 30 days is a stretch. Revised gate:
   2 paid pilots or 5 written commitments by day 45. Check any employment contract for side-business / IP clauses before selling.
3. **Replace "competitor watch".** Thin and legally risky if it drifts into scraping. Use what the repo does well:
   seasonality, pressure index, events, STR share, each with a one-line "so what". The interpretation is the product.
4. **Drop review intelligence and the consumer city guide for now.** Review tooling is crowded (ReviewPro, TrustYou, Revinate) and
   data rights are fragile; the city guide has the trip-length retention problem. Expand sideways instead (Balaton, Crete,
   host-facing seasonality calendar) using the same pipeline.

## Added
- Produce the same sample brief for Crete beside Budapest; STR-heavy markets may pay faster.
- Next concrete step: generate the sample Budapest brief from existing repo data and judge how much is genuinely useful vs freely available.

## Three routes to revenue from the existing build
1. Pressure reports for Greek and Hungarian regions/municipalities (one-off PDF/web, then subscription). Needs no forecasting edge.
2. Small developer API (pressure index, outlook ranges), e.g. on RapidAPI.
3. Host-facing seasonality calendar for Balaton/Crete, the bridge to the STR audience.

## Park until there is a paying customer
Traveler DNA, Destination Twin, knowledge graph, agent layer, Tourism Studio.
