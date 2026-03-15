"""Health check endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health(request: Request) -> dict:
    """Liveness probe — always returns 200 if the process is alive."""
    cfg = request.app.state.config
    return {
        "status": "ok",
        "version": cfg.app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/health/ready")
async def ready(request: Request) -> dict:
    """Readiness probe — 200 if engine is initialised, 503 otherwise."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return {"status": "not_ready", "reason": "engine not started"}
    return {"status": "ready"}
