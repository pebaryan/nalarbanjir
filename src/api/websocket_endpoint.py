"""Backward-compatible shim for the WebSocket endpoint.

Canonical implementation lives in ``src.api.websocket.simulation_ws``.
This module remains to avoid import breakage in older entry points.
"""
from __future__ import annotations

from src.api.websocket.simulation_ws import endpoint as websocket_endpoint

__all__ = ["websocket_endpoint"]
