"""
Feature extraction: convert simulation state into ML input tensors.

Features (10 per 2D cell):
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

All arrays are (nx, ny), dtype float32.
"""
from __future__ import annotations

import numpy as np

from src.physics.state import Solver2DState

_GRAVITY = 9.81
_EPS     = 1e-6


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


def normalise_features(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Z-score normalise feature matrix X.

    Returns:
        X_norm  — normalised (n_samples, n_features)
        mean    — (n_features,)
        std     — (n_features,)
    """
    mean = X.mean(axis=0)
    std  = X.std(axis=0)
    std  = np.where(std < _EPS, 1.0, std)  # avoid division by zero
    return (X - mean) / std, mean, std
