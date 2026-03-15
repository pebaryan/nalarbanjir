"""WebSocket endpoint for Flood Prediction World Model.

This module adds WebSocket support to the FastAPI server for real-time
communication with the frontend.
"""

from fastapi import WebSocket, WebSocketDisconnect
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Simple WebSocket connection manager."""

    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected. Total: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"WebSocket client disconnected. Total: {len(self.active_connections)}"
        )

    async def send_message(self, websocket: WebSocket, message: dict):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    await manager.connect(websocket)
    try:
        # Send welcome message
        await manager.send_message(
            websocket,
            {
                "type": "connection_established",
                "message": "Connected to Flood Prediction World Model",
                "timestamp": 0,
            },
        )

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle different message types
                if message.get("type") == "ping":
                    await manager.send_message(
                        websocket, {"type": "pong", "timestamp": 0}
                    )
                elif message.get("type") == "subscribe":
                    channel = message.get("channel", "all")
                    await manager.send_message(
                        websocket, {"type": "subscribed", "channel": channel}
                    )
                else:
                    # Echo back with acknowledgment
                    await manager.send_message(
                        websocket,
                        {
                            "type": "ack",
                            "received": message.get("type"),
                            "timestamp": 0,
                        },
                    )

            except json.JSONDecodeError:
                await manager.send_message(
                    websocket, {"type": "error", "message": "Invalid JSON"}
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
