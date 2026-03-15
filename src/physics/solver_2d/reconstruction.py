"""
MUSCL (Monotone Upstream-Centred Scheme for Conservation Laws) reconstruction
with minmod slope limiter for 2nd-order spatial accuracy.

The reconstruction extrapolates cell-centred values to cell faces, giving
2nd-order accuracy in smooth regions while limiting slopes near discontinuities
to prevent spurious oscillations (Godunov's theorem).

Minmod limiter: φ(r) = max(0, min(1, r))
  Conservative choice — reverts to 1st order near shocks, but always stable.
"""
from __future__ import annotations

import numpy as np


def minmod(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Element-wise minmod: returns the smaller-magnitude value if they have
    the same sign, otherwise 0.
    """
    return np.where(a * b > 0, np.where(np.abs(a) < np.abs(b), a, b), 0.0)


def reconstruct_x(
    q: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    MUSCL reconstruction in x-direction.

    For each interior cell (i, j), extrapolate to right face:
        q_right[i] = q[i] + 0.5 * slope[i]
        q_left[i+1] = q[i] - 0.5 * slope[i]   ← left state at face i+1/2

    Wait — let me clarify the convention:
        q_L[i+1/2] = value extrapolated rightward from cell i
        q_R[i+1/2] = value extrapolated leftward from cell i+1

    Args:
        q: Cell-centred values, shape (nx, ny)

    Returns:
        q_L: Left state at each face, shape (nx-1, ny)  — from cell i, face i+1/2
        q_R: Right state at each face, shape (nx-1, ny) — from cell i+1, face i+1/2
    """
    nx, ny = q.shape

    # Slopes at each cell using minmod of forward and backward differences
    dq_forward  = q[1:, :] - q[:-1, :]          # q[i+1] - q[i], shape (nx-1, ny)
    dq_backward = q[1:, :] - q[:-1, :]           # re-used below with offset

    # For interior cells 1..nx-2: slope = minmod(q[i]-q[i-1], q[i+1]-q[i])
    slope = np.zeros_like(q)
    if nx >= 3:
        left_diff  = q[1:-1, :] - q[:-2, :]    # q[i] - q[i-1], shape (nx-2, ny)
        right_diff = q[2:, :]   - q[1:-1, :]   # q[i+1] - q[i], shape (nx-2, ny)
        slope[1:-1, :] = minmod(left_diff, right_diff)
    # Boundary cells: slope = 0 (1st-order at boundaries)

    # Extrapolate to faces i+1/2
    q_L = q[:-1, :] + 0.5 * slope[:-1, :]   # from left cell
    q_R = q[1:, :]  - 0.5 * slope[1:, :]    # from right cell

    return q_L, q_R


def reconstruct_y(
    q: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    MUSCL reconstruction in y-direction.

    Args:
        q: Cell-centred values, shape (nx, ny)

    Returns:
        q_B: Bottom state at each face, shape (nx, ny-1)
        q_T: Top state at each face, shape (nx, ny-1)
    """
    nx, ny = q.shape

    slope = np.zeros_like(q)
    if ny >= 3:
        bot_diff = q[:, 1:-1] - q[:, :-2]
        top_diff = q[:, 2:]   - q[:, 1:-1]
        slope[:, 1:-1] = minmod(bot_diff, top_diff)

    q_B = q[:, :-1] + 0.5 * slope[:, :-1]
    q_T = q[:, 1:]  - 0.5 * slope[:, 1:]

    return q_B, q_T


def reconstruct_pair_x(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    z: np.ndarray,
    min_depth: float = 0.001,
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray,
    np.ndarray, np.ndarray, np.ndarray,
]:
    """
    Hydrostatic reconstruction in x for [h, u, v] with bed elevation z.

    The hydrostatic reconstruction ensures the well-balanced property (C-property):
    a lake at rest (η = z + h = const, u = v = 0) produces zero flux.

    Steps:
      1. Reconstruct η = z + h (free surface)
      2. Reconstruct z
      3. h_face = max(0, η_face - z_face)  — ensures positivity
      4. Reconstruct u, v only where h > ε

    Args:
        h: Water depth [m], shape (nx, ny)
        u: x-velocity [m/s], shape (nx, ny)
        v: y-velocity [m/s], shape (nx, ny)
        z: Bed elevation [m], shape (nx, ny)
        min_depth: Wet/dry threshold [m]

    Returns:
        h_L, u_L, v_L: Left states at x-faces, shape (nx-1, ny)
        h_R, u_R, v_R: Right states at x-faces, shape (nx-1, ny)
    """
    eta = z + h

    eta_L, eta_R = reconstruct_x(eta)
    z_L,   z_R   = reconstruct_x(z)
    u_L,   u_R   = reconstruct_x(u)
    v_L,   v_R   = reconstruct_x(v)

    # Positivity-preserving depth reconstruction
    h_L = np.maximum(0.0, eta_L - z_L)
    h_R = np.maximum(0.0, eta_R - z_R)

    # Zero velocity in dry cells
    u_L = np.where(h_L > min_depth, u_L, 0.0)
    u_R = np.where(h_R > min_depth, u_R, 0.0)
    v_L = np.where(h_L > min_depth, v_L, 0.0)
    v_R = np.where(h_R > min_depth, v_R, 0.0)

    return h_L, u_L, v_L, h_R, u_R, v_R


def reconstruct_pair_y(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    z: np.ndarray,
    min_depth: float = 0.001,
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray,
    np.ndarray, np.ndarray, np.ndarray,
]:
    """Hydrostatic reconstruction in y for [h, u, v]."""
    eta = z + h

    eta_B, eta_T = reconstruct_y(eta)
    z_B,   z_T   = reconstruct_y(z)
    u_B,   u_T   = reconstruct_y(u)
    v_B,   v_T   = reconstruct_y(v)

    h_B = np.maximum(0.0, eta_B - z_B)
    h_T = np.maximum(0.0, eta_T - z_T)

    u_B = np.where(h_B > min_depth, u_B, 0.0)
    u_T = np.where(h_T > min_depth, u_T, 0.0)
    v_B = np.where(h_B > min_depth, v_B, 0.0)
    v_T = np.where(h_T > min_depth, v_T, 0.0)

    return h_B, u_B, v_B, h_T, u_T, v_T
