"""
FastAPI lifespan hooks — startup and shutdown logic.

Usage in main.py:
    from src.core.events import lifespan
    app = FastAPI(lifespan=lifespan)
"""
from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _configure_logging(level: str, files: object) -> None:
    """Set up file + console logging handlers."""
    Path("logs").mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Startup:
      1. Load and validate config
      2. Configure logging
      3. Create data/log directories
      4. Initialize WebSocket manager (stored on app.state)

    Shutdown:
      1. Stop running simulation engine (if any)
      2. Close all WebSocket connections
    """
    # ── Startup ──────────────────────────────────────────────────────────
    from src.core.config import load_config

    config = load_config()
    app.state.config = config

    _configure_logging(config.logging.level, config.logging.files)
    logger.info("Nalarbanjir v%s starting up", config.app.version)
    logger.info(
        "Default solver mode: %s | grid: %dx%d",
        config.physics.default_mode,
        config.physics.solver_2d.nx,
        config.physics.solver_2d.ny,
    )

    # Ensure runtime directories exist
    for directory in ["logs", "data/primary", "data/archive", "ml/checkpoints"]:
        Path(directory).mkdir(parents=True, exist_ok=True)

    # WebSocket manager — imported here to avoid circular imports at module level
    from src.api.websocket.manager import WebSocketManager

    ws_manager = WebSocketManager(
        heartbeat_interval=config.api.websocket.heartbeat_interval,
    )
    app.state.ws_manager = ws_manager

    # No engine pre-created — engine is instantiated per POST /simulation/run
    app.state.engine = None
    # ML predictor is created lazily on first prediction request
    app.state.ml_predictor = None

    logger.info("Startup complete. API listening on %s:%d", config.api.host, config.api.port)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("Shutting down...")

    engine = getattr(app.state, "engine", None)
    if engine is not None:
        engine.pause()   # no-op; engine has no background task
        logger.info("Simulation engine stopped.")

    ws_manager = getattr(app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.close_all()
        logger.info("WebSocket connections closed.")

    logger.info("Shutdown complete.")
