"""
WebSocket endpoint for real-time simulation streaming.

Clients connect to /ws and exchange JSON messages:

  Client → Server:
    {"type": "ping"}
    {"type": "step", "n": 1}
    {"type": "run", "steps": 500, "yield_every": 5}
    {"type": "reset"}
    {"type": "status"}

  Server → Client:
    {"type": "pong"}
    {"type": "state",    "elapsed_time": ..., "step": ..., "data": {...}}
    {"type": "running",  "step": ..., "elapsed_time": ...}
    {"type": "complete", "steps": ..., "elapsed_time": ...}
    {"type": "reset_ok"}
    {"type": "status",   "elapsed_time": ..., "step": ...}
    {"type": "error",    "message": ...}
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from src.physics.state import Solver1DState, Solver2DState, CoupledState
from src.api.serializers import state_1d_to_response, state_2d_to_response

logger = logging.getLogger(__name__)

# Prevent two concurrent async runs on the same engine
_run_lock = asyncio.Lock()


async def endpoint(websocket: WebSocket) -> None:
    """Main WebSocket handler — registered at /ws in main.py."""
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type", "unknown")

            if msg_type == "ping":
                await ws_manager.send(websocket, {"type": "pong"})

            elif msg_type == "status":
                engine = websocket.app.state.engine
                if engine is None:
                    await ws_manager.send(websocket, {
                        "type": "status", "engine": "not_started",
                    })
                else:
                    await ws_manager.send(websocket, {
                        "type": "status",
                        "elapsed_time": engine.current_time,
                        "step": getattr(websocket.app.state, "step_count", 0),
                    })

            elif msg_type == "step":
                engine = websocket.app.state.engine
                if engine is None:
                    await ws_manager.send(websocket, {
                        "type": "error", "message": "Engine not started",
                    })
                    continue
                n = int(raw.get("n", 1))
                for _ in range(n):
                    engine.step()
                step_count = getattr(websocket.app.state, "step_count", 0) + n
                websocket.app.state.step_count = step_count
                await ws_manager.send(websocket, {
                    "type": "state",
                    "step": step_count,
                    "elapsed_time": engine.current_time,
                    "data": _serialize_state(engine),
                })

            elif msg_type == "run":
                engine = websocket.app.state.engine
                if engine is None:
                    await ws_manager.send(websocket, {
                        "type": "error", "message": "Engine not started",
                    })
                    continue
                steps = int(raw.get("steps", 100))
                yield_every = int(raw.get("yield_every", 10))
                async with _run_lock:
                    step_count = getattr(websocket.app.state, "step_count", 0)
                    async for _ in engine.run(steps=steps, yield_every=yield_every):
                        step_count += yield_every
                        websocket.app.state.step_count = step_count
                        await ws_manager.broadcast({
                            "type": "running",
                            "step": step_count,
                            "elapsed_time": engine.current_time,
                        })
                    await ws_manager.broadcast({
                        "type": "complete",
                        "steps": steps,
                        "elapsed_time": engine.current_time,
                    })

            elif msg_type == "reset":
                engine = websocket.app.state.engine
                if engine is None:
                    await ws_manager.send(websocket, {
                        "type": "error", "message": "Engine not started",
                    })
                    continue
                engine.reset()
                websocket.app.state.step_count = 0
                await ws_manager.send(websocket, {"type": "reset_ok"})

            else:
                await ws_manager.send(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("WS handler error: %s", exc)
    finally:
        ws_manager.disconnect(websocket)


def _serialize_state(engine) -> dict:
    """Convert engine state to a JSON-safe dict."""
    raw = engine.state
    out: dict = {}
    if isinstance(raw, CoupledState):
        out["state_1d"] = state_1d_to_response(raw.state_1d).model_dump()
        out["state_2d"] = state_2d_to_response(raw.state_2d).model_dump()
    elif isinstance(raw, Solver2DState):
        out["state_2d"] = state_2d_to_response(raw).model_dump()
    elif isinstance(raw, Solver1DState):
        out["state_1d"] = state_1d_to_response(raw).model_dump()
    return out
