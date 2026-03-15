"""
Simulation control endpoints.

POST /api/simulation/start          — create and initialise a SimulationEngine
GET  /api/simulation/status         — current mode, time, step count
POST /api/simulation/step?n=1       — advance N steps synchronously
GET  /api/simulation/state          — full serialised state
POST /api/simulation/reset          — reset engine to t=0
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from src.core.config import get_config
from src.physics.engine import SimulationEngine
from src.physics.state import Solver1DState, Solver2DState, CoupledState
from src.api.dependencies import get_engine
from src.api.serializers import (
    state_1d_to_response,
    state_2d_to_response,
    compute_flood_stats,
)
from src.api.schemas.simulation import (
    RunRequest,
    SimulationStatusResponse,
    SimulationStateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["simulation"])


class StartResponse(BaseModel):
    ok: bool
    mode: str
    message: str


# ── Start ──────────────────────────────────────────────────────────────────

@router.post("/start", response_model=StartResponse)
async def start(body: RunRequest, request: Request) -> StartResponse:
    """
    Initialise (or re-initialise) the simulation engine with the given mode.

    For modes '1d' and '1d2d' a default single-reach network is created.
    A more complex network can be configured separately (future endpoint).
    """
    cfg = request.app.state.config
    mode = body.mode

    engine = SimulationEngine(mode=mode, config=cfg)

    if mode in ("1d", "1d2d"):
        from src.physics.solver_1d.cross_section import CrossSection
        from src.physics.solver_1d.network import ChannelNetwork

        cs = CrossSection.rectangular(
            width=20.0, z_bed=0.0, bank_height=8.0
        )
        network = ChannelNetwork.simple_reach(
            n_cross_sections=20,
            reach_length=5000.0,
            cross_section=cs,
            slope=0.001,
            upstream_Q=50.0,
            downstream_h=4.0,
        )
        engine.initialize(network=network)
    else:
        engine.initialize()

    request.app.state.engine = engine
    request.app.state.step_count = 0

    logger.info("Simulation started: mode=%s", mode)
    return StartResponse(ok=True, mode=mode, message=f"Engine initialised in mode '{mode}'")


# ── Status ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=SimulationStatusResponse)
async def status(
    request: Request,
    engine: SimulationEngine = Depends(get_engine),
) -> SimulationStatusResponse:
    step_count = getattr(request.app.state, "step_count", 0)
    total = getattr(request.app.state, "total_steps", 0)
    return SimulationStatusResponse(
        status="idle",
        current_step=step_count,
        total_steps=total,
        elapsed_time=engine.current_time,
    )


# ── Step ───────────────────────────────────────────────────────────────────

@router.post("/step", response_model=SimulationStateResponse)
async def step(
    request: Request,
    n: int = Query(1, ge=1, le=1000, description="Number of steps to advance"),
    engine: SimulationEngine = Depends(get_engine),
) -> SimulationStateResponse:
    """Advance the simulation by N steps and return the new state."""
    for _ in range(n):
        engine.step()

    step_count = getattr(request.app.state, "step_count", 0) + n
    request.app.state.step_count = step_count

    return _engine_state_response(engine)


# ── State ──────────────────────────────────────────────────────────────────

@router.get("/state", response_model=SimulationStateResponse)
async def get_state(request: Request) -> SimulationStateResponse:
    """Return current simulation state, or an idle empty state if not started."""
    engine: SimulationEngine | None = request.app.state.engine
    if engine is None:
        from src.api.schemas.simulation import SimulationStateResponse
        return SimulationStateResponse(
            mode="2d", status="idle", current_step=0, elapsed_time=0.0,
            state_1d=None, state_2d=None, stats=None,
        )
    return _engine_state_response(engine)


# ── Reset ──────────────────────────────────────────────────────────────────

@router.post("/reset")
async def reset(
    request: Request,
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    engine.reset()
    request.app.state.step_count = 0
    return {"ok": True, "message": "Engine reset to t=0"}


# ── Helpers ────────────────────────────────────────────────────────────────

def _engine_state_response(engine: SimulationEngine) -> SimulationStateResponse:
    """Build a SimulationStateResponse from the engine's current state."""
    raw = engine.state
    mode = engine.mode

    state_1d = None
    state_2d = None
    stats = None

    if isinstance(raw, CoupledState):
        state_1d = state_1d_to_response(raw.state_1d)
        state_2d = state_2d_to_response(raw.state_2d)
        stats = compute_flood_stats(raw.state_2d)
    elif isinstance(raw, Solver2DState):
        state_2d = state_2d_to_response(raw)
        stats = compute_flood_stats(raw)
    elif isinstance(raw, Solver1DState):
        state_1d = state_1d_to_response(raw)

    return SimulationStateResponse(
        mode=mode,
        status="idle",
        current_step=0,
        elapsed_time=engine.current_time,
        state_2d=state_2d,
        state_1d=state_1d,
        stats=stats,
    )
