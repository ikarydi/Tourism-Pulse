from fastapi import FastAPI

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