"""
Conversion helpers: physics state objects → Pydantic response schemas.

Kept separate from routes to make serialization logic independently testable.
"""
from __future__ import annotations

import numpy as np

from src.core.config import get_config
from src.physics.state import Solver1DState, Solver2DState, CoupledState, SimulationState
from src.api.schemas.simulation import (
    Solver1DStateResponse,
    Solver2DStateResponse,
    FloodStats,
    RiskLevel,
)


def _dominant_risk(flood_risk: np.ndarray) -> RiskLevel:
    labels: list[RiskLevel] = ["none", "minor", "moderate", "major", "severe"]
    return labels[min(int(np.max(flood_risk)), 4)]


def state_1d_to_response(state: Solver1DState) -> Solver1DStateResponse:
    return Solver1DStateResponse(
        chainage=state.chainage.tolist(),
        discharge=state.discharge.tolist(),
        water_surface_elev=state.water_surface_elev.tolist(),
        velocity=state.velocity.tolist(),
        node_ids=list(state.node_ids),
    )


def state_2d_to_response(state: Solver2DState) -> Solver2DStateResponse:
    return Solver2DStateResponse(
        water_depth=state.water_depth.tolist(),
        velocity_x=state.velocity_x.tolist(),
        velocity_y=state.velocity_y.tolist(),
        flood_risk=state.flood_risk.astype(int).tolist(),
    )


def compute_flood_stats(state: Solver2DState) -> FloodStats:
    cfg = get_config()
    dx, dy = cfg.physics.solver_2d.dx, cfg.physics.solver_2d.dy
    h = state.water_depth
    wet_mask = h > cfg.terrain.flood_thresholds.minor
    max_depth = float(np.max(h))
    mean_depth = float(np.mean(h[wet_mask])) if np.any(wet_mask) else 0.0
    flooded_cells = int(np.sum(wet_mask))
    flooded_area_km2 = flooded_cells * dx * dy / 1e6
    return FloodStats(
        max_depth=max_depth,
        mean_depth=mean_depth,
        flooded_cells=flooded_cells,
        flooded_area_km2=flooded_area_km2,
        dominant_risk=_dominant_risk(state.flood_risk),
    )
