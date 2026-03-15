"""Pydantic v2 schemas for simulation endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SimulationMode = Literal["1d", "2d", "1d2d"]
SimulationStatus = Literal["idle", "running", "paused", "completed", "error"]
RainfallPattern = Literal["uniform", "storm_cell", "frontal"]
RiskLevel = Literal["none", "minor", "moderate", "major", "severe"]


# ── Requests ──────────────────────────────────────────────────────────────


class RainfallParams(BaseModel):
    pattern: RainfallPattern = "uniform"
    intensity: float = Field(0.0, ge=0, description="Rainfall intensity [m/s]")
    duration: float = Field(3600.0, gt=0, description="Duration [s]")
    storm_x: float | None = Field(None, description="Storm cell center x [m]")
    storm_y: float | None = Field(None, description="Storm cell center y [m]")


class RunRequest(BaseModel):
    mode: SimulationMode = "2d"
    steps: int = Field(1000, gt=0, le=100_000, description="Number of simulation steps")
    rainfall: RainfallParams = Field(default_factory=RainfallParams)
    broadcast_interval: int = Field(5, gt=0, description="Emit WebSocket update every N steps")
    dem_file_id: str | None = Field(None, description="GIS file_id of a DEM to use as solver terrain")

    model_config = {
        "json_schema_extra": {
            "example": {
                "mode": "2d",
                "steps": 500,
                "rainfall": {
                    "pattern": "storm_cell",
                    "intensity": 5e-5,
                    "duration": 1800,
                    "storm_x": 5000,
                    "storm_y": 5000,
                },
                "broadcast_interval": 5,
            }
        }
    }


# ── Response fragments ────────────────────────────────────────────────────


class FloodStats(BaseModel):
    max_depth: float = Field(..., ge=0, description="Maximum water depth [m]")
    mean_depth: float = Field(..., ge=0, description="Mean water depth over wet cells [m]")
    flooded_cells: int = Field(..., ge=0)
    flooded_area_km2: float = Field(..., ge=0, description="Inundated area [km²]")
    dominant_risk: RiskLevel


class Solver2DStateResponse(BaseModel):
    """Serialized 2D solver state — grids flattened to nested lists for JSON."""
    water_depth: list[list[float]]   # [nx][ny], meters
    velocity_x: list[list[float]]    # [nx][ny], m/s
    velocity_y: list[list[float]]    # [nx][ny], m/s
    flood_risk: list[list[int]]      # [nx][ny], 0–4


class Solver1DStateResponse(BaseModel):
    """Serialized 1D solver state — parallel arrays indexed by node."""
    chainage: list[float]              # [m] along reach
    discharge: list[float]             # Q [m³/s]
    water_surface_elev: list[float]    # h [m a.s.l.]
    velocity: list[float]              # V [m/s]
    node_ids: list[str]


# ── Responses ─────────────────────────────────────────────────────────────


class SimulationStateResponse(BaseModel):
    mode: SimulationMode
    status: SimulationStatus
    current_step: int = Field(..., ge=0)
    elapsed_time: float = Field(..., ge=0, description="Simulation time [s]")
    state_2d: Solver2DStateResponse | None = None
    state_1d: Solver1DStateResponse | None = None
    stats: FloodStats | None = None


class SimulationStatusResponse(BaseModel):
    status: SimulationStatus
    current_step: int
    total_steps: int
    elapsed_time: float


# ── WebSocket messages ────────────────────────────────────────────────────


class WsSimulationUpdate(BaseModel):
    """Emitted every broadcast_interval steps during a run."""
    type: Literal["simulation_update"] = "simulation_update"
    step: int
    mode: SimulationMode
    elapsed_time: float
    data: SimulationStateResponse


class WsSimulationComplete(BaseModel):
    """Emitted once when simulation reaches total_steps."""
    type: Literal["simulation_complete"] = "simulation_complete"
    total_steps: int
    elapsed_time: float
    stats: FloodStats


class WsError(BaseModel):
    """Emitted on solver error."""
    type: Literal["error"] = "error"
    code: str
    message: str


class WsPing(BaseModel):
    type: Literal["ping"] = "ping"


class WsPong(BaseModel):
    type: Literal["pong"] = "pong"
