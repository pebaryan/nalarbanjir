"""Backward-compatible shim for the WebSocket manager.

Canonical implementation lives in ``src.api.websocket.manager``.
This module remains to avoid import breakage in older entry points.
"""
from __future__ import annotations

from src.api.websocket.manager import WebSocketManager

__all__ = ["WebSocketManager"]
