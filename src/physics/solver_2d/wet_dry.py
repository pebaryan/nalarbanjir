"""
Wet/dry front treatment for the 2D shallow water solver.

Wet/dry fronts (the leading edge of a flood wave advancing over dry land)
are numerically challenging because:
  - Water depth → 0 continuously
  - Velocity can become unbounded as h → 0 in momentum variables
  - Naive schemes produce negative depths

This module implements:
  1. Depth floor: h ≥ 0 enforced after every step
  2. Momentum zeroing: hu, hv = 0 where h < ε
  3. Froude limiting: cap velocity to prevent super-critical instabilities
  4. Bed slope balancing: hydrostatic reconstruction (see reconstruction.py)
"""
from __future__ import annotations

import numpy as np

_GRAVITY = 9.81


def apply_wet_dry(
    h: np.ndarray,
    hu: np.ndarray,
    hv: np.ndarray,
    min_depth: float = 0.001,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Enforce positivity and zero momentum in dry cells.

    Args:
        h:  Water depth [m],         shape (nx, ny)
        hu: x-momentum h·u [m²/s],  shape (nx, ny)
        hv: y-momentum h·v [m²/s],  shape (nx, ny)
        min_depth: Wet/dry threshold [m]

    Returns:
        h, hu, hv — corrected in-place.
    """
    # 1. Floor depth to zero (no negative depths)
    h = np.maximum(h, 0.0)

    # 2. Zero momentum in dry cells
    wet = h > min_depth
    hu = np.where(wet, hu, 0.0)
    hv = np.where(wet, hv, 0.0)

    return h, hu, hv


def extract_velocities(
    h: np.ndarray,
    hu: np.ndarray,
    hv: np.ndarray,
    min_depth: float = 0.001,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract u = hu/h, v = hv/h safely (zero in dry cells).

    Args:
        h:  Water depth [m]
        hu: x-momentum [m²/s]
        hv: y-momentum [m²/s]
        min_depth: Threshold below which velocity is set to zero

    Returns:
        u, v — velocity components [m/s]
    """
    h_safe = np.where(h > min_depth, h, 1.0)   # avoid division by zero
    u = np.where(h > min_depth, hu / h_safe, 0.0)
    v = np.where(h > min_depth, hv / h_safe, 0.0)
    return u, v


def limit_froude(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    max_froude: float = 5.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Cap velocity so Froude number does not exceed max_froude.
    Prevents runaway acceleration in very thin water layers.

    Args:
        h: Water depth [m]
        u, v: Velocity components [m/s]
        max_froude: Maximum allowable Froude number (default 5.0)

    Returns:
        u, v — Froude-limited velocities.
    """
    c = np.sqrt(_GRAVITY * np.maximum(h, 1e-9))
    speed = np.sqrt(u**2 + v**2)
    max_speed = max_froude * c

    # Scale down velocity vector if speed exceeds limit
    scale = np.where(speed > max_speed, max_speed / np.maximum(speed, 1e-12), 1.0)
    return u * scale, v * scale


def compute_cfl_dt(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    dx: float,
    dy: float,
    cfl: float = 0.9,
    min_depth: float = 0.001,
) -> float:
    """
    Compute the CFL-stable time step.

    Δt = CFL * min(dx, dy) / max(|u| + c, |v| + c)
    where c = sqrt(g*h) is the wave speed.

    Args:
        h, u, v: Current state arrays, shape (nx, ny)
        dx, dy:  Cell sizes [m]
        cfl:     CFL safety factor (0 < cfl ≤ 1)
        min_depth: Threshold for wet cells

    Returns:
        dt: Maximum stable time step [s].
    """
    wet = h > min_depth
    if not np.any(wet):
        return 1.0  # all dry — arbitrary dt

    c = np.sqrt(_GRAVITY * np.where(wet, h, 0.0))

    max_speed_x = np.max(np.where(wet, np.abs(u) + c, 0.0))
    max_speed_y = np.max(np.where(wet, np.abs(v) + c, 0.0))

    max_speed_x = max(max_speed_x, 1e-9)
    max_speed_y = max(max_speed_y, 1e-9)

    dt_x = cfl * dx / max_speed_x
    dt_y = cfl * dy / max_speed_y

    return min(dt_x, dt_y)
