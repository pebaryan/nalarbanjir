"""
Lateral exchange flux between the 1D channel and the 2D floodplain.

Uses the broad-crested weir formula:

    Q_ex = Cd · L · √(2g) · (Δh)^1.5

where:
    Cd  = weir coefficient (dimensionless, typically 0.3–0.5)
    L   = weir (cell) width [m]
    Δh  = max(0, η_upstream - z_bank)  [m]

Sign convention:
    Q_ex > 0  →  flow from channel to floodplain
    Q_ex < 0  →  return flow from floodplain to channel
"""
from __future__ import annotations

import numpy as np

_GRAVITY = 9.81
_SQRT_2G = float(np.sqrt(2.0 * _GRAVITY))


def compute_exchange(
    wse_1d: np.ndarray,          # WSE at 1D interface nodes [m a.s.l.]
    wse_2d: np.ndarray,          # WSE at adjacent 2D cells [m a.s.l.]
    bank_elevations: np.ndarray, # z_bank [m a.s.l.] at each interface point
    cell_width: float,           # weir length L [m] (typically dy or dx)
    weir_coeff: float = 0.4,
) -> np.ndarray:
    """
    Compute lateral exchange flux [m³/s] at each interface point.

    Returns an array of signed discharges:
      positive → channel overflows to floodplain
      negative → floodplain drains back to channel
    """
    # Head over the bank crest on each side
    h_over_bank_1d = np.maximum(0.0, wse_1d - bank_elevations)
    h_over_bank_2d = np.maximum(0.0, wse_2d - bank_elevations)

    # Weir discharge magnitudes
    q_ch_to_fp = weir_coeff * cell_width * _SQRT_2G * h_over_bank_1d ** 1.5
    q_fp_to_ch = weir_coeff * cell_width * _SQRT_2G * h_over_bank_2d ** 1.5

    # Net exchange: flow direction follows the higher water surface
    exchange = np.where(
        wse_1d >= wse_2d,
        q_ch_to_fp,    # channel higher → overflow to floodplain
        -q_fp_to_ch,   # floodplain higher → return to channel
    )
    return exchange


def apply_exchange_to_2d(
    h_2d: np.ndarray,       # shape (nx, ny), modified IN PLACE
    exchange: np.ndarray,   # shape (n_points,), [m³/s]; positive = gain
    i_indices: np.ndarray,  # shape (n_points,), int
    j_indices: np.ndarray,  # shape (n_points,), int
    dt: float,
    dx: float,
    dy: float,
) -> None:
    """
    Add exchange volume to 2D cells.

    dh = Q_ex · dt / (dx · dy)  — depth increment per cell [m]
    No-negative-depth guard is applied after accumulation.
    """
    dh = exchange * dt / (dx * dy)
    np.add.at(h_2d, (i_indices, j_indices), dh)
    np.maximum(h_2d, 0.0, out=h_2d)


def apply_exchange_to_1d_Q(
    Q_1d: np.ndarray,         # shape (n_nodes,), modified IN PLACE
    exchange: np.ndarray,     # shape (n_points,), [m³/s]; positive = lose
    node_indices: np.ndarray, # shape (n_points,), int
) -> None:
    """
    Subtract lateral overflow from 1D discharge at interface nodes.

    A positive exchange (channel → floodplain) reduces Q at that node.
    """
    np.add.at(Q_1d, node_indices, -exchange)
