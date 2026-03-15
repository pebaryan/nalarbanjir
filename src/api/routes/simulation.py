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

import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from src.core.config import NalarbanjirConfig, get_config
from src.physics.engine import SimulationEngine
from src.physics.solver_2d.finite_volume import Solver2D
from src.physics.state import Solver1DState, Solver2DState, CoupledState
from src.api.dependencies import get_engine
from src.api.serializers import (
    state_1d_to_response,
    state_2d_to_response,
    compute_flood_stats,
)
from src.api.schemas.simulation import (
    RainfallParams,
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

    # Apply rainfall to the 2D solver (was previously ignored)
    if mode in ("2d", "1d2d") and engine._solver_2d is not None:
        _apply_rainfall(engine._solver_2d, body.rainfall, cfg)

    request.app.state.engine = engine
    request.app.state.step_count = 0

    logger.info(
        "Simulation started: mode=%s rainfall=%s intensity=%.2e m/s",
        mode, body.rainfall.pattern, body.rainfall.intensity,
    )
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

def _apply_rainfall(solver: Solver2D, params: RainfallParams, cfg: NalarbanjirConfig) -> None:
    """Compute and set the rainfall source array on the 2D solver."""
    nx, ny, dx, dy = solver.nx, solver.ny, solver.dx, solver.dy
    solver._rain[:] = 0.0

    if params.intensity <= 0:
        return

    if params.pattern == "uniform":
        solver._rain[:] = params.intensity

    elif params.pattern == "storm_cell":
        sigma = cfg.rainfall.storm_cell.sigma
        cx = params.storm_x if params.storm_x is not None else nx * dx / 2.0
        cy = params.storm_y if params.storm_y is not None else ny * dy / 2.0
        x = (np.arange(nx) + 0.5) * dx
        y = (np.arange(ny) + 0.5) * dy
        xx, yy = np.meshgrid(x, y, indexing="ij")
        r2 = (xx - cx) ** 2 + (yy - cy) ** 2
        solver._rain[:] = params.intensity * np.exp(-r2 / (2.0 * sigma ** 2))

    elif params.pattern == "frontal":
        # Intensity ramps linearly from zero (west) to full (east)
        x = (np.arange(nx) + 0.5) * dx
        gradient = x / (nx * dx)          # 0 … 1 along x-axis
        solver._rain[:] = params.intensity * gradient[:, np.newaxis]


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
