"""WebSocket layer — FastAPI-native manager + simulation endpoint."""
from __future__ import annotations

from src.api.websocket.manager import WebSocketManager
from src.api.websocket.simulation_ws import endpoint as simulation_endpoint

__all__ = ["WebSocketManager", "simulation_endpoint"]
