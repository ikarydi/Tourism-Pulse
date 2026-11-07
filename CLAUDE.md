# Tourism Pulse
Tourism-pressure observatory and 12-month seasonal outlook for EU destinations (Crete and Hungary first).
- Strategy docs: `docs/strategy/`. Plan: Notion Masterplan, group Tourism Pulse.

## Phase (update when gates pass)
- Product focus is the **pressure observatory**. Forecasts ship as a seasonal outlook with intervals.
- Pre-registered research gates 1, 1b, 2 (skill) and 3 FAILED. Make no alternative-data accuracy claims anywhere: UI, copy, pitches, the paper.
- Gate 4 (does YouTube upload growth help at 4-12 months?) was pre-registered on 2026-11-07, before any social data was fetched. Its live holdout is scored around Mar 2028. Until then, social signals are context only.
- Now:
  - put the read-only scoreboard online
  - post the preprint
  - write to the Crete Tourism Observatory
  - do 15 interviews (5 by 31 Dec 2026)
- Gate (27 Mar 2027): live error vs the 4.96% backtest, and 3 pilots. If missed: stop product work, publish the paper, keep the record running.
- Scope rule: do not build master-spec modules (Traveler DNA, Destination Twin, knowledge graph, agents, Tourism Studio) unless a pilot asks for one.

## Stack
- API: Python 3.12, FastAPI, SQLAlchemy 2, Alembic (`infrastructure/alembic`), APScheduler, Groq. Lives in `apps/api`.
- DB: Postgres with PostGIS and pgvector (`infrastructure/postgres`).
- Web: React + TypeScript + Vite, in `apps/web`.
- About 20 ingestion adapters: Eurostat, KSH, EC survey, Wikipedia, GDELT, OpenSky, Eurocontrol, weather, and more. Social media: YouTube monthly uploads, Reddit and Bluesky (official APIs; monthly aggregates only, no post text or usernames stored).

## Commands
```
make test        # pytest; uses an isolated <db>_test database, never the .env one
make lint        # ruff check
make format      # ruff format
make run         # uvicorn API with reload
make scheduler   # ingestion scheduler
```
- Web: `cd apps/web && npm install && npm run dev`
- Read-only local DB for Claude: the `db` server in `.mcp.json` (postgres-mcp, restricted mode; needs `uv`). Claude Code asks once before enabling it.

## Rules
- The pulse engine is deterministic: no ML or LLM in scores. Every score carries confidence, freshness and lineage.
- Airbnb and Booking.com stay stubs. No scraping of sites without a public API or licence.
- Every record stores its source and fetch time. Each adapter gets a contract test that alerts on format changes.
- Forecasts are published to `tourism-pulse-forecasts`, append-only, with SHA-256 and an RFC 3161 token. Never revise a published batch. A method change gets a new model version.
- Any new research question gets a pre-registered gate before data is examined.
