from fastapi import FastAPI
from sqlalchemy import text

from tourism_pulse_api.db.session import engine
from tourism_pulse_api.routers.attractions import router as attractions_router
from tourism_pulse_api.routers.destinations import router as destinations_router
from tourism_pulse_api.routers.places import router as places_router
from tourism_pulse_api.routers.place import router as place_router
from tourism_pulse_api.routers.signals import router as signals_router
from tourism_pulse_api.routers.events import router as events_router
from tourism_pulse_api.routers.pulse import router as pulse_router

app = FastAPI(
    title="Tourism Pulse API",
    description="AI-powered tourism intelligence platform",
    version="0.1.0",
)

app.include_router(destinations_router)
app.include_router(places_router)
app.include_router(attractions_router)
app.include_router(place_router)
app.include_router(signals_router)
app.include_router(events_router)
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
