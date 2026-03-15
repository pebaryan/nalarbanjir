"""
FastAPI-native WebSocket connection manager.

Uses FastAPI's built-in WebSocket type (no extra `websockets` package needed).
Supports broadcasting to all connected clients and direct send to one.
"""
from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages a list of active FastAPI WebSocket connections."""

    def __init__(self, heartbeat_interval: int = 30) -> None:
        self.heartbeat_interval = heartbeat_interval
        self._connections: list[WebSocket] = []

    # ── Connection lifecycle ───────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await ws.accept()
        self._connections.append(ws)
        logger.info("WS connected  total=%d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a connection (idempotent)."""
        try:
            self._connections.remove(ws)
        except ValueError:
            pass
        logger.info("WS disconnected  total=%d", len(self._connections))

    async def close_all(self) -> None:
        """Close all connections — called on application shutdown."""
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        logger.info("All WebSocket connections closed")

    # ── Messaging ─────────────────────────────────────────────────────────

    async def send(self, ws: WebSocket, payload: dict) -> None:
        """Send a JSON payload to one client. Disconnects on error."""
        try:
            await ws.send_json(payload)
        except Exception as exc:
            logger.error("WS send error: %s", exc)
            self.disconnect(ws)

    async def broadcast(self, payload: dict) -> None:
        """Send a JSON payload to all connected clients."""
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def n_connections(self) -> int:
        return len(self._connections)
