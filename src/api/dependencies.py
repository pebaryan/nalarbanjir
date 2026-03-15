"""
FastAPI dependency functions for injecting app-level singletons.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from src.physics.engine import SimulationEngine
from src.api.websocket.manager import WebSocketManager


def get_engine(request: Request) -> SimulationEngine:
    """Inject the active SimulationEngine or raise 409 if not started."""
    engine: SimulationEngine | None = request.app.state.engine
    if engine is None:
        raise HTTPException(
            status_code=409,
            detail="No simulation started. POST /api/simulation/start first.",
        )
    return engine


def get_ws_manager(request: Request) -> WebSocketManager:
    """Inject the app-level WebSocketManager."""
    return request.app.state.ws_manager
