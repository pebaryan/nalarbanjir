"""
Feature extraction: convert simulation state into ML input tensors.

2D Features (10 per cell):
  0  water_depth          h [m]
  1  velocity_u           u [m/s]
  2  velocity_v           v [m/s]
  3  speed                |u| [m/s]
  4  bed_elevation        z [m]
  5  water_surface_elev   η = z + h [m]
  6  froude_number        Fr = |u| / √(g·h)
  7  grad_h_x             ∂h/∂x (central difference)
  8  grad_h_y             ∂h/∂y
  9  flood_risk_physics   physics-derived risk class (0-4)

1D Features (10 per node) — same schema, adapted for 1D channel data:
  0  equivalent_depth     A / T  (hydraulic depth, proxy for water_depth)
  1  velocity             V [m/s]
  2  0                    (no transverse velocity)
  3  abs(velocity)        |V| [m/s]
  4  bed_elevation        η - hydraulic_depth
  5  water_surface_elev   η [m]
  6  froude_number        Fr
  7  dQ_dc                discharge gradient along chainage
  8  0                    (no transverse gradient)
  9  flood_risk_physics   derived from depth & Froude

All arrays are float32.
"""
from __future__ import annotations

import numpy as np

from src.physics.state import Solver1DState, Solver2DState

_GRAVITY = 9.81
_EPS     = 1e-6
# Risk thresholds (depth in metres): 0=none, 1=minor, 2=moderate, 3=major, 4=severe
_RISK_THRESHOLDS = [0.0, 0.3, 1.0, 2.0, 5.0]


def _classify_risk(depth: float, froude: float) -> int:
    """Classify flood risk 0-4 from depth [m] and Froude number."""
    if depth < _RISK_THRESHOLDS[1]:
        return 0
    if depth < _RISK_THRESHOLDS[2]:
        return 1
    if depth < _RISK_THRESHOLDS[3]:
        return 2
    if depth < _RISK_THRESHOLDS[4] or froude < 1.0:
        return 3
    return 4


def extract_features(state: Solver2DState) -> np.ndarray:
    """
    Build feature matrix from a Solver2DState.

    Returns array of shape (nx * ny, 10) — one row per cell, float32.
    """
    h  = state.water_depth
    u  = state.velocity_x
    v  = state.velocity_y
    z  = state.bed_elevation
    fr = state.flood_risk.astype(np.float32)

    nx, ny = h.shape
    eta    = z + h
    speed  = np.sqrt(u**2 + v**2)
    c      = np.sqrt(_GRAVITY * np.maximum(h, _EPS))
    froude = speed / c

    # Spatial gradients (central differences, zero-padded at boundary)
    gx = np.gradient(h, axis=0)
    gy = np.gradient(h, axis=1)

    stack = np.stack([h, u, v, speed, z, eta, froude, gx, gy, fr], axis=-1)
    # shape (nx, ny, 10) → (nx*ny, 10)
    return stack.reshape(-1, 10).astype(np.float32)


def extract_features_1d(state: Solver1DState) -> np.ndarray:
    """
    Build feature matrix from a Solver1DState (1D channel nodes).

    Maps 1D hydraulic quantities into the same 10-feature schema used
    by the 2D path so the model can share weights.

    Returns array of shape (n_nodes, 10) — one row per node, float32.
    """
    Q   = state.discharge           # [m³/s]
    eta = state.water_surface_elev  # [m]
    A   = state.area                # [m²]
    V   = state.velocity            # [m/s]
    c   = state.chainage            # [m]

    n = state.n_nodes
    # Hydraulic depth = A / top_width; approximate top_width as A / hydraulic_depth → iterative
    # Simpler: hydraulic_depth ≈ A / sqrt(A) = sqrt(A)  (rectangular approx)
    # Better: use top_width ≈ 2 * sqrt(A) for trapezoidal channel
    top_width = np.maximum(2.0 * np.sqrt(np.maximum(A, _EPS)), 1e-6)
    hyd_depth = A / top_width  # ≈ sqrt(A) / 2

    # Bed elevation = water surface - depth
    bed = eta - hyd_depth

    # Froude number
    celerity = np.sqrt(_GRAVITY * np.maximum(hyd_depth, _EPS))
    speed = np.abs(V)
    froude = speed / celerity

    # Discharge gradient along chainage
    if n > 1:
        dQ_dc = np.gradient(Q, c)
    else:
        dQ_dc = np.zeros(1)

    # Risk classification
    risk = np.array([_classify_risk(float(hyd_depth[i]), float(froude[i]))
                     for i in range(n)], dtype=np.float32)

    features = np.column_stack([
        hyd_depth,    # 0: equivalent_depth
        V,            # 1: velocity (signed, replaces u)
        np.zeros(n),  # 2: no transverse velocity
        speed,        # 3: abs velocity
        bed,          # 4: bed_elevation
        eta,          # 5: water_surface_elev
        froude,       # 6: froude_number
        dQ_dc,        # 7: longitudinal gradient (replaces grad_h_x)
        np.zeros(n),  # 8: no transverse gradient
        risk,         # 9: flood_risk
    ])
    return features.astype(np.float32)


def normalise_features(X: np.ndarray, mean: np.ndarray | None = None,
                       std: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Z-score normalise feature matrix X.

    If mean/std are provided they are reused (e.g. from training stats).
    Otherwise they are computed from X.

    Returns:
        X_norm  — normalised (n_samples, n_features)
        mean    — (n_features,)
        std     — (n_features,)
    """
    if mean is None:
        mean = X.mean(axis=0)
    if std is None:
        std  = X.std(axis=0)
    std  = np.where(std < _EPS, 1.0, std)
    return (X - mean) / std, mean, std
