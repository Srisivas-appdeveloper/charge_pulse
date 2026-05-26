"""FastAPI app entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts.router import router as alerts_router
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.chargers.router import router as chargers_router
from app.config import get_settings
from app.db.session import close_pool, get_pool
from app.fleet.router import router as fleet_router
from app.incidents.router import router as incidents_router
from app.ws import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="ChargePulse API",
    version="0.2.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(chargers_router, prefix=API_PREFIX)
app.include_router(incidents_router, prefix=API_PREFIX)
app.include_router(alerts_router, prefix=API_PREFIX)
app.include_router(fleet_router, prefix=API_PREFIX)
app.include_router(analytics_router, prefix=API_PREFIX)
app.include_router(ws_router, prefix=API_PREFIX)
