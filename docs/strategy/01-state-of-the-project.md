# State of the project (as of commit 77bc0ef, 2026-09-28)

## What exists
- **API**: Python, Postgres (PostGIS + pgvector), ~35 Alembic migrations.
- **Web**: React/TypeScript. Pages: Dashboard, Europe Map, Observatory, Outlook, Attention, Explore, region detail.
- **~20 ingestion adapters**: Eurostat (national, regional, bulk), KSH (Hungary), EC business survey,
  Wikipedia, GDELT, YouTube, OpenSky, Eurocontrol, weather, OpenAQ, GDACS, OSM, Ticketmaster.
  Airbnb and Booking.com are deliberately stubs (no public API; scraping refused).
- **Pulse engine**: deterministic destination score with confidence, freshness, lineage and narrative. No ML/LLM.
- **Tourism-pressure observatory**: ranks a destination against every European region at the same NUTS level
  on tourism intensity, density, peak-month concentration and STR share, with economic dependence shown separately.
- **12-month outlook**: 273 places. Batches are published to the public `tourism-pulse-forecasts` repo with
  SHA-256 hashes and RFC 3161 timestamps so forecasts can be scored after Eurostat publishes.

## Research verdicts (pre-registered)
| Gate | Question | Result |
|---|---|---|
| 1 (countries, phase 1+2) | Do Wikipedia/GDELT improve current-month nowcasts? | FAIL (13/30, 15/30; need 16) |
| 1b (Hungarian areas) | Same, sub-national | FAIL (5/12; need 7) |
| 2 | Does attention help forecasts 4-12 months ahead? | Attention test PASS (26/30, median ratio 0.936); skill vs seasonal-naive FAIL (5/30) |
| 3 | Do flights or the hotel survey help at 1-3 months? | FAIL (flights 16/30, survey 6/25 and worse) |

Consequences: no alternative-data accuracy claim; forecasts shipped as a seasonal outlook with intervals;
place-level forecasts (Budapest, Balaton, etc.) are `validated: no`; the pressure observatory is the product focus.

## Strengths
- Timestamped forecast record and pre-registered tests: rare credibility in this market.
- Observatory fits the overtourism / STR-regulation agenda.

## Risks
- Scope sprawl: the master spec covers Traveler DNA, Destination Twin, knowledge graph, three agents, Tourism Studio.
- No proprietary demand data; edge is methodology and interpretation, not the forecasts.
- Public bodies buy slowly (procurement cycles).
- Much of the raw data is free (KSH, Eurostat); the product is the "so what".
