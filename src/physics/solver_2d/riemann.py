"""
HLLE (Harten-Lax-van Leer-Einfeldt) Riemann solver for the 2D shallow water equations.

The HLLE solver computes the numerical flux at a cell face given left and right states.
It guarantees positivity of water depth and correct wave speeds, making it stable
for both sub- and super-critical flows and across wet/dry fronts.

Reference: Einfeldt et al. (1991), "On Godunov-type methods near low densities"
"""
from __future__ import annotations

import numpy as np

_GRAVITY = 9.81
_EPS = 1e-9  # prevent division by zero


def hlle_flux_x(
    h_l: np.ndarray,
    u_l: np.ndarray,
    v_l: np.ndarray,
    h_r: np.ndarray,
    u_r: np.ndarray,
    v_r: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute HLLE flux in the x-direction at a vertical cell face.

    State vector: U = [h, hu, hv]
    Flux vector:  F = [hu, hu² + ½gh², huv]

    Args:
        h_l, u_l, v_l: Left-state water depth [m], x-velocity [m/s], y-velocity [m/s]
        h_r, u_r, v_r: Right-state counterparts

    Returns:
        (F_h, F_hu, F_hv): Numerical flux components, same shape as inputs.
    """
    g = _GRAVITY

    # Wave speed estimates (Einfeldt)
    c_l = np.sqrt(g * np.maximum(h_l, _EPS))
    c_r = np.sqrt(g * np.maximum(h_r, _EPS))

    s_l = np.minimum(u_l - c_l, u_r - c_r)
    s_r = np.maximum(u_l + c_l, u_r + c_r)

    # Avoid division by zero when s_l == s_r (stationary wave)
    ds = np.where(np.abs(s_r - s_l) > _EPS, s_r - s_l, _EPS)

    # Left and right fluxes F(U_L), F(U_R)
    f_h_l  = h_l * u_l
    f_hu_l = h_l * u_l**2 + 0.5 * g * h_l**2
    f_hv_l = h_l * u_l * v_l

    f_h_r  = h_r * u_r
    f_hu_r = h_r * u_r**2 + 0.5 * g * h_r**2
    f_hv_r = h_r * u_r * v_r

    # Conserved variables
    hu_l = h_l * u_l;  hv_l = h_l * v_l
    hu_r = h_r * u_r;  hv_r = h_r * v_r

    # HLLE flux: F = (s_R·F_L - s_L·F_R + s_L·s_R·(U_R - U_L)) / (s_R - s_L)
    coeff = s_l * s_r / ds

    f_h  = (s_r * f_h_l  - s_l * f_h_r  + coeff * (h_r  - h_l))  / 1.0
    f_hu = (s_r * f_hu_l - s_l * f_hu_r + coeff * (hu_r - hu_l)) / 1.0
    f_hv = (s_r * f_hv_l - s_l * f_hv_r + coeff * (hv_r - hv_l)) / 1.0

    # Normalise by (s_R - s_L)
    f_h  = (s_r * f_h_l  - s_l * f_h_r  + s_l * s_r * (h_r  - h_l))  / ds
    f_hu = (s_r * f_hu_l - s_l * f_hu_r + s_l * s_r * (hu_r - hu_l)) / ds
    f_hv = (s_r * f_hv_l - s_l * f_hv_r + s_l * s_r * (hv_r - hv_l)) / ds

    # Pure upwind when both waves travel in same direction
    f_h  = np.where(s_l >= 0, f_h_l,  np.where(s_r <= 0, f_h_r,  f_h))
    f_hu = np.where(s_l >= 0, f_hu_l, np.where(s_r <= 0, f_hu_r, f_hu))
    f_hv = np.where(s_l >= 0, f_hv_l, np.where(s_r <= 0, f_hv_r, f_hv))

    return f_h, f_hu, f_hv


def hlle_flux_y(
    h_b: np.ndarray,
    u_b: np.ndarray,
    v_b: np.ndarray,
    h_t: np.ndarray,
    u_t: np.ndarray,
    v_t: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute HLLE flux in the y-direction at a horizontal cell face.

    Flux vector: G = [hv, huv, hv² + ½gh²]
    By symmetry, swap (u↔v, hu↔hv) and call hlle_flux_x.

    Args:
        h_b, u_b, v_b: Bottom-state (lower y index)
        h_t, u_t, v_t: Top-state (higher y index)

    Returns:
        (G_h, G_hu, G_hv): Numerical flux components.
    """
    # Rotate: treat v as the normal velocity, u as tangential
    g_h, g_hv, g_hu = hlle_flux_x(h_b, v_b, u_b, h_t, v_t, u_t)
    return g_h, g_hu, g_hv
