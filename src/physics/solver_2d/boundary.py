"""
Boundary condition applicators for the 2D finite-volume solver.

Boundary conditions are implemented by populating ghost cells outside the domain
with appropriate values before each flux computation.

Supported types:
  - REFLECTIVE:   zero normal velocity, reflected tangential (solid wall)
  - OPEN:         zero-gradient (Neumann) — extrapolate interior → exterior
  - INFLOW:       prescribed h and velocity at boundary
  - OUTFLOW:      zero-gradient with depth floor (subcritical outflow)
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable

import numpy as np


class BCType(Enum):
    REFLECTIVE = "reflective"
    OPEN       = "open"
    INFLOW     = "inflow"
    OUTFLOW    = "outflow"


@dataclass
class BoundaryConditions:
    """
    Container for boundary conditions on all four sides.

    Each side can have a different type and optional prescribed values.
    'west'  = x=0 edge
    'east'  = x=nx-1 edge
    'south' = y=0 edge
    'north' = y=ny-1 edge
    """
    west:  BCType = BCType.REFLECTIVE
    east:  BCType = BCType.REFLECTIVE
    south: BCType = BCType.REFLECTIVE
    north: BCType = BCType.REFLECTIVE

    # Optional: prescribed h, u, v for INFLOW boundaries
    # Dict keyed by side name, value = (h, u, v) scalars or callable(t) -> (h, u, v)
    inflow_values: dict[str, tuple] = field(default_factory=dict)


def apply_boundary_conditions(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    bc: BoundaryConditions,
    t: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply boundary conditions by modifying the outermost cell layer.

    This implements ghost-cell BCs directly on the solution arrays.
    For flux computation, the MUSCL reconstruction already uses boundary slopes = 0,
    so these cells act as ghost cells for the face reconstruction.

    Args:
        h, u, v: Solution arrays, shape (nx, ny)
        bc: BoundaryConditions specification
        t: Current simulation time [s] (used for time-varying inflow)

    Returns:
        Modified h, u, v arrays.
    """
    h, u, v = _apply_side(h, u, v, bc.west,  "west",  bc.inflow_values, t)
    h, u, v = _apply_side(h, u, v, bc.east,  "east",  bc.inflow_values, t)
    h, u, v = _apply_side(h, u, v, bc.south, "south", bc.inflow_values, t)
    h, u, v = _apply_side(h, u, v, bc.north, "north", bc.inflow_values, t)
    return h, u, v


def _apply_side(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    bc_type: BCType,
    side: str,
    inflow_values: dict,
    t: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if bc_type == BCType.REFLECTIVE:
        return _reflective(h, u, v, side)
    elif bc_type == BCType.OPEN:
        return _open(h, u, v, side)
    elif bc_type == BCType.INFLOW:
        return _inflow(h, u, v, side, inflow_values.get(side, (0.0, 0.0, 0.0)), t)
    elif bc_type == BCType.OUTFLOW:
        return _outflow(h, u, v, side)
    return h, u, v


def _reflective(h, u, v, side):
    """Solid wall: zero normal velocity, copy tangential."""
    if side == "west":
        h[0, :] = h[1, :]
        u[0, :] = -u[1, :]   # reflect normal
        v[0, :] = v[1, :]
    elif side == "east":
        h[-1, :] = h[-2, :]
        u[-1, :] = -u[-2, :]
        v[-1, :] = v[-2, :]
    elif side == "south":
        h[:, 0] = h[:, 1]
        u[:, 0] = u[:, 1]
        v[:, 0] = -v[:, 1]
    elif side == "north":
        h[:, -1] = h[:, -2]
        u[:, -1] = u[:, -2]
        v[:, -1] = -v[:, -2]
    return h, u, v


def _open(h, u, v, side):
    """Zero-gradient (Neumann): copy interior cell value to boundary."""
    if side == "west":
        h[0, :] = h[1, :];  u[0, :] = u[1, :];  v[0, :] = v[1, :]
    elif side == "east":
        h[-1, :] = h[-2, :]; u[-1, :] = u[-2, :]; v[-1, :] = v[-2, :]
    elif side == "south":
        h[:, 0] = h[:, 1];  u[:, 0] = u[:, 1];  v[:, 0] = v[:, 1]
    elif side == "north":
        h[:, -1] = h[:, -2]; u[:, -1] = u[:, -2]; v[:, -1] = v[:, -2]
    return h, u, v


def _outflow(h, u, v, side):
    """Outflow: zero-gradient depth, ensure velocity points outward."""
    h, u, v = _open(h, u, v, side)
    if side == "west":
        u[0, :] = np.minimum(u[0, :], 0.0)   # only allow inward = negative u, block reversal
    elif side == "east":
        u[-1, :] = np.maximum(u[-1, :], 0.0)
    elif side == "south":
        v[:, 0] = np.minimum(v[:, 0], 0.0)
    elif side == "north":
        v[:, -1] = np.maximum(v[:, -1], 0.0)
    return h, u, v


def _inflow(h, u, v, side, values, t):
    """Prescribed h, u, v at boundary. values may be (scalar, scalar, scalar) or callable."""
    if callable(values):
        h_in, u_in, v_in = values(t)
    else:
        h_in, u_in, v_in = values
    if side == "west":
        h[0, :] = h_in;  u[0, :] = u_in;  v[0, :] = v_in
    elif side == "east":
        h[-1, :] = h_in; u[-1, :] = u_in; v[-1, :] = v_in
    elif side == "south":
        h[:, 0] = h_in;  u[:, 0] = u_in;  v[:, 0] = v_in
    elif side == "north":
        h[:, -1] = h_in; u[:, -1] = u_in; v[:, -1] = v_in
    return h, u, v
