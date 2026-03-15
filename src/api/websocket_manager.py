"""WebSocket manager for real-time communication.

This module provides WebSocket connection management, broadcasting,
and real-time data streaming capabilities for the flood prediction system.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

try:
    import websockets
    from websockets.server import WebSocketServerProtocol

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = Any

logger = logging.getLogger(__name__)


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""

    message_type: str
    data: Dict[str, Any]
    timestamp: str
    session_id: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections and broadcasting."""

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocketServerProtocol] = set()
        self.connection_metadata: Dict[WebSocketServerProtocol, Dict] = {}
        self.subscribers: Dict[str, Set[WebSocketServerProtocol]] = {
            "simulation": set(),
            "visualization": set(),
            "predictions": set(),
            "alerts": set(),
            "all": set(),
        }
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

        if not WEBSOCKETS_AVAILABLE:
            logger.warning(
                "websockets package not available. WebSocket functionality disabled."
            )

    async def connect(
        self, websocket: WebSocketServerProtocol, client_info: Dict = None
    ):
        """Register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            client_info: Optional client metadata
        """
        if not WEBSOCKETS_AVAILABLE:
            logger.error("WebSocket support not available")
            return

        self.active_connections.add(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "client_info": client_info or {},
            "subscriptions": {"all"},
        }
        self.subscribers["all"].add(websocket)

        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

        # Send welcome message
        await self.send_personal_message(
            websocket,
            {
                "type": "connection_established",
                "message": "Connected to Flood Prediction World Model",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(self.active_connections),
            },
        )

    def disconnect(self, websocket: WebSocketServerProtocol):
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove
        """
        if not WEBSOCKETS_AVAILABLE:
            return

        self.active_connections.discard(websocket)

        # Remove from all subscription channels
        for channel in self.subscribers.values():
            channel.discard(websocket)

        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]

        logger.info(
            f"Client disconnected. Total connections: {len(self.active_connections)}"
        )

    async def send_personal_message(
        self, websocket: WebSocketServerProtocol, message: Dict
    ):
        """Send a message to a specific client.

        Args:
            websocket: Target WebSocket connection
            message: Message to send
        """
        if not WEBSOCKETS_AVAILABLE:
            return

        try:
            if websocket in self.active_connections:
                await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict, channel: str = "all"):
        """Broadcast a message to all subscribed clients.

        Args:
            message: Message to broadcast
            channel: Subscription channel ('simulation', 'visualization', 'predictions', 'alerts', 'all')
        """
        if not WEBSOCKETS_AVAILABLE:
            return

        if channel not in self.subscribers:
            logger.warning(f"Unknown channel: {channel}")
            return

        disconnected = set()
        message_json = json.dumps(message)

        for connection in self.subscribers[channel]:
            try:
                await connection.send(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    def subscribe(self, websocket: WebSocketServerProtocol, channel: str):
        """Subscribe a client to a channel.

        Args:
            websocket: Client WebSocket connection
            channel: Channel to subscribe to
        """
        if not WEBSOCKETS_AVAILABLE:
            return

        if channel in self.subscribers:
            self.subscribers[channel].add(websocket)
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["subscriptions"].add(channel)
            logger.info(f"Client subscribed to channel: {channel}")

    def unsubscribe(self, websocket: WebSocketServerProtocol, channel: str):
        """Unsubscribe a client from a channel.

        Args:
            websocket: Client WebSocket connection
            channel: Channel to unsubscribe from
        """
        if not WEBSOCKETS_AVAILABLE:
            return

        if channel in self.subscribers:
            self.subscribers[channel].discard(websocket)
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["subscriptions"].discard(channel)
            logger.info(f"Client unsubscribed from channel: {channel}")

    async def handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming WebSocket messages.

        Args:
            websocket: Client connection
            message: Received message
        """
        if not WEBSOCKETS_AVAILABLE:
            return

        try:
            data = json.loads(message)
            message_type = data.get("type", "unknown")

            if message_type == "subscribe":
                channel = data.get("channel", "all")
                self.subscribe(websocket, channel)
                await self.send_personal_message(
                    websocket, {"type": "subscribed", "channel": channel}
                )

            elif message_type == "unsubscribe":
                channel = data.get("channel", "all")
                self.unsubscribe(websocket, channel)
                await self.send_personal_message(
                    websocket, {"type": "unsubscribed", "channel": channel}
                )

            elif message_type == "ping":
                await self.send_personal_message(
                    websocket, {"type": "pong", "timestamp": datetime.now().isoformat()}
                )

            elif message_type == "get_status":
                await self.send_personal_message(
                    websocket,
                    {
                        "type": "status",
                        "active_connections": len(self.active_connections),
                        "subscriptions": {
                            channel: len(subscribers)
                            for channel, subscribers in self.subscribers.items()
                        },
                    },
                )

            else:
                # Handle custom message types
                await self.send_personal_message(
                    websocket,
                    {
                        "type": "ack",
                        "received_type": message_type,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
            await self.send_personal_message(
                websocket, {"type": "error", "message": "Invalid JSON format"}
            )
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def get_connection_stats(self) -> Dict:
        """Get connection statistics.

        Returns:
            Connection statistics dictionary
        """
        return {
            "total_connections": len(self.active_connections),
            "subscriptions": {
                channel: len(subscribers)
                for channel, subscribers in self.subscribers.items()
            },
            "connection_details": [
                {
                    "connected_at": meta.get("connected_at"),
                    "client_info": meta.get("client_info"),
                    "subscriptions": list(meta.get("subscriptions", set())),
                }
                for meta in self.connection_metadata.values()
            ],
        }


class RealTimeDataStreamer:
    """Streams real-time simulation data via WebSockets."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the data streamer.

        Args:
            connection_manager: Connection manager instance
        """
        self.connection_manager = connection_manager
        self._streaming = False
        self._stream_task = None

    async def start_streaming(self, data_source, interval: float = 1.0):
        """Start streaming data to connected clients.

        Args:
            data_source: Callable that returns data to stream
            interval: Streaming interval in seconds
        """
        self._streaming = True

        while self._streaming:
            try:
                # Get latest data
                data = (
                    await data_source()
                    if asyncio.iscoroutinefunction(data_source)
                    else data_source()
                )

                # Prepare message
                message = {
                    "type": "simulation_update",
                    "timestamp": datetime.now().isoformat(),
                    "data": self._serialize_data(data),
                }

                # Broadcast to simulation channel
                await self.connection_manager.broadcast(message, "simulation")

                # Wait before next update
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in streaming loop: {e}")
                await asyncio.sleep(interval)

    def stop_streaming(self):
        """Stop the data streaming."""
        self._streaming = False
        logger.info("Data streaming stopped")

    def _serialize_data(self, data: Any) -> Any:
        """Serialize data for JSON transmission.

        Args:
            data: Data to serialize

        Returns:
            JSON-serializable data
        """
        if isinstance(data, np.ndarray):
            return data.tolist()
        elif isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif hasattr(data, "isoformat"):  # datetime
            return data.isoformat()
        else:
            return data

    async def send_alert(
        self, alert_type: str, message: str, severity: str = "info", data: Dict = None
    ):
        """Send an alert to all connected clients.

        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Alert severity ('info', 'warning', 'critical')
            data: Additional alert data
        """
        alert = {
            "type": "alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }

        await self.connection_manager.broadcast(alert, "alerts")
        logger.info(f"Alert sent: [{severity}] {message}")

    async def send_prediction_update(self, prediction_data: Dict):
        """Send prediction update to subscribed clients.

        Args:
            prediction_data: Prediction data to send
        """
        message = {
            "type": "prediction_update",
            "timestamp": datetime.now().isoformat(),
            "predictions": self._serialize_data(prediction_data),
        }

        await self.connection_manager.broadcast(message, "predictions")

    async def send_visualization_update(self, visualization_data: Dict):
        """Send visualization update to subscribed clients.

        Args:
            visualization_data: Visualization data to send
        """
        message = {
            "type": "visualization_update",
            "timestamp": datetime.now().isoformat(),
            "visualization": self._serialize_data(visualization_data),
        }

        await self.connection_manager.broadcast(message, "visualization")


# Global connection manager instance
connection_manager = ConnectionManager()


async def websocket_handler(websocket: WebSocketServerProtocol, path: str):
    """Handle WebSocket connections.

    Args:
        websocket: WebSocket connection
        path: Connection path
    """
    if not WEBSOCKETS_AVAILABLE:
        logger.error("WebSocket support not available")
        return

    client_info = {
        "path": path,
        "remote_address": getattr(websocket, "remote_address", None),
    }

    await connection_manager.connect(websocket, client_info)

    try:
        async for message in websocket:
            await connection_manager.handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
    finally:
        connection_manager.disconnect(websocket)


def start_websocket_server(host: str = "0.0.0.0", port: int = 8765):
    """Start the WebSocket server.

    Args:
        host: Host to bind to
        port: Port to listen on

    Returns:
        WebSocket server instance
    """
    if not WEBSOCKETS_AVAILABLE:
        logger.error("Cannot start WebSocket server: websockets package not installed")
        return None

    logger.info(f"Starting WebSocket server on {host}:{port}")

    return websockets.serve(websocket_handler, host, port)


# Convenience functions for broadcasting
async def broadcast_simulation_update(data: Dict):
    """Broadcast simulation update to all subscribers."""
    await connection_manager.broadcast(
        {
            "type": "simulation_update",
            "timestamp": datetime.now().isoformat(),
            "data": data,
        },
        "simulation",
    )


async def broadcast_alert(alert_type: str, message: str, severity: str = "info"):
    """Broadcast alert to all subscribers."""
    await connection_manager.broadcast(
        {
            "type": "alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
        },
        "alerts",
    )
