"""
Simulation state dataclasses.

These are the canonical data containers passed between the physics engine,
API layer, and WebSocket serializer. Kept as plain dataclasses (no FastAPI/Pydantic
dependency) so the physics layer stays framework-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

SimulationMode = Literal["1d", "2d", "1d2d"]


# ── 2D Solver State ───────────────────────────────────────────────────────


@dataclass
class Solver2DState:
    """
    State of the 2D finite-volume solver on a structured (nx × ny) grid.

    All arrays use shape (nx, ny) with row = x-index, col = y-index.
    """

    # Primary hydraulic variables
    water_depth: np.ndarray    # h  [m],   shape (nx, ny)
    velocity_x: np.ndarray     # u  [m/s], shape (nx, ny)
    velocity_y: np.ndarray     # v  [m/s], shape (nx, ny)

    # Bed elevation — constant after initialization
    bed_elevation: np.ndarray  # z  [m],   shape (nx, ny)

    # Rainfall source at current time step
    rainfall_rate: np.ndarray  # [m/s],    shape (nx, ny)

    # Flood risk classification — integer 0–4
    # 0=none, 1=minor, 2=moderate, 3=major, 4=severe
    flood_risk: np.ndarray     # int8,     shape (nx, ny)

    @property
    def water_surface_elevation(self) -> np.ndarray:
        """Free-surface elevation η = z + h [m]."""
        return self.bed_elevation + self.water_depth

    @property
    def speed(self) -> np.ndarray:
        """Flow speed |u| = sqrt(u² + v²) [m/s]."""
        return np.sqrt(self.velocity_x**2 + self.velocity_y**2)

    @property
    def froude_number(self) -> np.ndarray:
        """Froude number Fr = |u| / sqrt(g·h). Inf where h = 0."""
        c = np.sqrt(9.81 * np.maximum(self.water_depth, 1e-9))
        return self.speed / c

    @property
    def nx(self) -> int:
        return int(self.water_depth.shape[0])

    @property
    def ny(self) -> int:
        return int(self.water_depth.shape[1])

    @property
    def total_volume(self) -> float:
        """Total water volume in domain [m³]. Used for mass conservation checks."""
        # dx * dy comes from the solver; here we return the raw h-sum for testing
        return float(np.sum(self.water_depth))


# ── 1D Solver State ───────────────────────────────────────────────────────


@dataclass
class CrossSectionState:
    """State at a single 1D cross-section node (for per-node queries)."""

    node_id: str
    chainage: float            # distance along reach [m]
    discharge: float           # Q [m³/s]
    water_surface_elev: float  # h [m a.s.l.]
    area: float                # A [m²]
    velocity: float            # V = Q/A [m/s]
    froude: float              # Fr = V / sqrt(g * hydraulic_depth)


@dataclass
class Solver1DState:
    """
    State of the 1D Preissmann solver across the full channel network.

    Arrays are ordered by node index in the network graph.
    """

    # Per-node arrays — shape (n_nodes,)
    chainage: np.ndarray             # [m]    distance along reach
    discharge: np.ndarray            # [m³/s] Q at each node
    water_surface_elev: np.ndarray   # [m]    h (water surface elevation)
    area: np.ndarray                 # [m²]   cross-sectional area A
    velocity: np.ndarray             # [m/s]  V = Q/A

    # Metadata
    node_ids: list[str] = field(default_factory=list)
    reach_ids: list[str] = field(default_factory=list)

    @property
    def n_nodes(self) -> int:
        return int(self.discharge.shape[0])

    @property
    def max_discharge(self) -> float:
        return float(np.max(np.abs(self.discharge)))

    @property
    def max_depth(self) -> float:
        """Maximum flow depth (not water surface elevation)."""
        return float(np.max(self.water_surface_elev))

    def get_node(self, node_id: str) -> CrossSectionState | None:
        """Return state at a specific node by ID."""
        if node_id not in self.node_ids:
            return None
        i = self.node_ids.index(node_id)
        h = float(self.water_surface_elev[i])
        Q = float(self.discharge[i])
        A = float(self.area[i])
        V = Q / A if A > 1e-9 else 0.0
        D = A / max(1e-9, A)   # hydraulic depth approx
        Fr = abs(V) / max(1e-9, (9.81 * D) ** 0.5)
        return CrossSectionState(
            node_id=node_id,
            chainage=float(self.chainage[i]),
            discharge=Q,
            water_surface_elev=h,
            area=A,
            velocity=V,
            froude=Fr,
        )


# ── Coupled State ─────────────────────────────────────────────────────────


@dataclass
class CoupledState:
    """
    Combined state for 1D+2D coupled simulation.

    Holds references to both sub-solver states plus the exchange flux array
    at the bank interface.
    """

    state_1d: Solver1DState
    state_2d: Solver2DState

    # Exchange flux at each bank interface cell [m³/s]
    # Positive = flow from channel to floodplain
    exchange_flux: np.ndarray   # shape (n_interface_cells,)

    @property
    def total_exchange_volume(self) -> float:
        """Cumulative exchange volume [m³] (positive = net to floodplain)."""
        return float(np.sum(self.exchange_flux))


# ── Type alias ────────────────────────────────────────────────────────────

# Used throughout the API and engine layers
SimulationState = Solver1DState | Solver2DState | CoupledState
