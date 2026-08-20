from fastapi import FastAPI
from sqlalchemy import text

from tourism_pulse_api.db.session import engine

app = FastAPI(
    title="Tourism Pulse API",
    description="AI-powered tourism intelligence platform",
    version="0.1.0",
)


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