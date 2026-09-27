from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from tourism_pulse_api.db.session import engine
from tourism_pulse_api.routers.attractions import router as attractions_router
from tourism_pulse_api.routers.demographics import router as demographics_router
from tourism_pulse_api.routers.destinations import router as destinations_router
from tourism_pulse_api.routers.events import router as events_router
from tourism_pulse_api.routers.lineage import router as lineage_router
from tourism_pulse_api.routers.news import router as news_router
from tourism_pulse_api.routers.observatory import router as observatory_router
from tourism_pulse_api.routers.place import router as place_router
from tourism_pulse_api.routers.places import router as places_router
from tourism_pulse_api.routers.pulse import router as pulse_router
from tourism_pulse_api.routers.signals import router as signals_router
from tourism_pulse_api.routers.videos import router as videos_router

app = FastAPI(
    title="Tourism Pulse API",
    description="AI-powered tourism intelligence platform",
    version="0.1.0",
)

# The Vite dev server proxies /api/* same-origin (vite.config.ts), so CORS
# has never been needed for local dev - but nothing enforced it for a real
# deploy where the frontend isn't served through that proxy. Open for now
# (no auth/cookies to protect yet - spec section 27 Authentication is still
# unbuilt); tighten allow_origins once a real frontend origin is deployed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(destinations_router)
app.include_router(places_router)
app.include_router(attractions_router)
app.include_router(place_router)
app.include_router(signals_router)
app.include_router(events_router)
app.include_router(news_router)
app.include_router(videos_router)
app.include_router(demographics_router)
app.include_router(lineage_router)
app.include_router(observatory_router)
app.include_router(pulse_router)

@app.get("/")
async def root() -> dict[str, str]:
    return {
        "application": "Tourism Pulse",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def database_health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"status": "ok"}
