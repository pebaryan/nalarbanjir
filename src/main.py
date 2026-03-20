"""
Nalarbanjir FastAPI application factory.

Usage:
    uvicorn src.main:app --reload

Or programmatically:
    from src.main import create_app
    app = create_app()
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_config
from src.core.events import lifespan
from src.api.routes import health, simulation, terrain, prediction, gis, layers, rivers
from src.api.websocket import simulation_ws


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = get_config()

    app = FastAPI(
        title="Nalarbanjir Flood Prediction API",
        description=(
            "1D/2D/1D+2D coupled hydraulic solver with AI-assisted flood "
            "prediction for Indonesian watersheds."
        ),
        version=cfg.app.version,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # HTTP routes
    app.include_router(health.router)
    app.include_router(simulation.router, prefix="/api/simulation")
    app.include_router(terrain.router,    prefix="/api/terrain")
    app.include_router(prediction.router, prefix="/api/prediction")
    app.include_router(gis.router,        prefix="/api/gis")
    app.include_router(layers.router,     prefix="/api/layers")
    app.include_router(rivers.router,     prefix="/api/rivers")

    # WebSocket
    app.add_api_websocket_route("/ws", simulation_ws.endpoint)

    return app


# Module-level app instance for uvicorn / gunicorn
app = create_app()
