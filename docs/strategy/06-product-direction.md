# Product direction: sell the evidence, not the forecast (2026-11-12)

Full proposal: https://claude.ai/artifact/Lgr8s7GZWJGJNVFGHWdm12

## Decision proposed
- **Free:** a public Pressure Index ranking every European region, with the forecast scoreboard. Marketing.
- **Paid:** the Destination Pressure Brief, a citable 8-10 page document for one destination
  (`python -m tourism_pulse_api.briefs`), with a licence to reuse its figures.
- **First buyer:** tourism consultants, planners and grant writers in Greece and Hungary. Municipalities second,
  through them (Greek direct award allows up to EUR 30,000 without a tender, law 4412/2016 art. 118).
- **Price hypotheses (untested):** Brief EUR 190 once; Monitor EUR 39/month per destination; Studio EUR 990/year
  for consultancies; custom study EUR 1,500-5,000.

## Why now
- Greece's draft Special Spatial Framework for Tourism (presented 11 May 2026) sorts 1,035 municipal units into five
  categories mainly by hotel beds per resident, without short-term-rental capacity. Adoption status not confirmed.
- Regulation (EU) 2024/1028 on short-term-rental data applied from 20 May 2026.

## Licence findings (terms read 2026-11-12; see `tourism_pulse_api/licensing.py`)
- Cleared for paid output: Eurostat, GISCO, KSH (published content), GDELT, Wikimedia pageviews (CC0).
- Not cleared: OpenSky, EUROCONTROL, Open-Meteo free tier, Ticketmaster, YouTube, Reddit. Unverified: OpenAQ, Bluesky, OSM, GDACS.
- YouTube's developer policies bar derived metrics and storage beyond 30 days without audited approval.
  This conflicts with Gate 4 as pre-registered and needs a decision, separately from selling.

## Still open
Buyer choice, price points, invoicing entity and VAT, Gate 4 and YouTube, payment account.
