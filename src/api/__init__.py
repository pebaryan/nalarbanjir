"""API module for Flood Prediction World Model.

This module provides API endpoints, WebSocket support, and request handling
for the flood prediction system.
"""

from .websocket_manager import (
    ConnectionManager,
    RealTimeDataStreamer,
    websocket_handler,
    start_websocket_server,
    connection_manager,
    broadcast_simulation_update,
    broadcast_alert,
)

__all__ = [
    "ConnectionManager",
    "RealTimeDataStreamer",
    "websocket_handler",
    "start_websocket_server",
    "connection_manager",
    "broadcast_simulation_update",
    "broadcast_alert",
]
