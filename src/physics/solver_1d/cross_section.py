"""
Cross-section geometry for the 1D Saint-Venant solver.

A cross-section is defined by surveyed (y, z) points where:
  y = transverse distance from left bank [m]
  z = bed elevation at that point [m a.s.l.]

For a given water surface elevation h_ws, we compute:
  A(h_ws) — wetted cross-sectional area [m²]
  P(h_ws) — wetted perimeter [m]
  T(h_ws) — top width [m]
  R(h_ws) = A/P — hydraulic radius [m]

These are pre-computed into lookup tables (arrays indexed by water level)
for fast evaluation during the implicit solve.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class CrossSection:
    """
    A single surveyed cross-section.

    Args:
        y_points: Transverse coordinates [m], monotonically increasing
        z_points: Bed elevation at each y point [m a.s.l.]
        manning_n: Manning roughness coefficient
        bank_left_z:  Left bank crest elevation [m]
        bank_right_z: Right bank crest elevation [m]
    """
    y_points: np.ndarray    # shape (n_points,)
    z_points: np.ndarray    # shape (n_points,)
    manning_n: float = 0.03
    bank_left_z: float = 0.0
    bank_right_z: float = 0.0

    # Lookup table resolution
    _n_levels: int = field(default=200, repr=False)
    _h_table: np.ndarray = field(default=None, repr=False)   # water surface levels
    _A_table: np.ndarray = field(default=None, repr=False)
    _P_table: np.ndarray = field(default=None, repr=False)
    _T_table: np.ndarray = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.y_points = np.asarray(self.y_points, dtype=float)
        self.z_points = np.asarray(self.z_points, dtype=float)
        assert len(self.y_points) == len(self.z_points) >= 3, \
            "Cross-section needs at least 3 survey points"
        assert np.all(np.diff(self.y_points) > 0), "y_points must be strictly increasing"

        self.z_min = float(np.min(self.z_points))
        self.z_max = float(max(self.bank_left_z, self.bank_right_z))
        if self.z_max <= self.z_min:
            self.z_max = self.z_min + 10.0  # fallback

        self._build_lookup_tables()

    def _build_lookup_tables(self) -> None:
        """Pre-compute A, P, T as functions of water surface elevation."""
        n = self._n_levels
        h_levels = np.linspace(self.z_min, self.z_max, n)
        A = np.zeros(n)
        P = np.zeros(n)
        T = np.zeros(n)

        for k, h_ws in enumerate(h_levels):
            a, p, t = self._compute_geometry(h_ws)
            A[k] = a
            P[k] = p
            T[k] = t

        self._h_table = h_levels
        self._A_table = A
        self._P_table = P
        self._T_table = T

    def _compute_geometry(self, h_ws: float) -> tuple[float, float, float]:
        """
        Compute A, P, T at water surface elevation h_ws by trapezoidal integration.

        Uses signed depths to correctly find bank/water-surface intersections.
        For each survey segment, identifies the wet portion and computes:
          - A: trapezoidal (or triangular) area between z and h_ws
          - P: slant length of the wet bed boundary
          - T: horizontal top-width contribution
        """
        y = self.y_points
        z = self.z_points
        n_pts = len(y)

        # Signed depth: positive = submerged, negative = above water
        d_signed = h_ws - z   # NOT clipped to 0

        if np.all(d_signed <= 0):
            return 0.0, 0.0, 0.0

        A_total = 0.0
        P_total = 0.0
        T_total = 0.0

        for i in range(n_pts - 1):
            y0, y1 = y[i], y[i + 1]
            z0, z1 = z[i], z[i + 1]
            d0, d1 = d_signed[i], d_signed[i + 1]
            dy = y1 - y0
            dz_bed = z1 - z0   # change in bed elevation

            if d0 <= 0 and d1 <= 0:
                continue   # both dry

            if d0 >= 0 and d1 >= 0:
                # Both wet — trapezoid
                A_total += 0.5 * (d0 + d1) * dy
                P_total += np.sqrt(dy**2 + dz_bed**2)
                T_total += dy

            elif d0 > 0 and d1 < 0:
                # Left wet, right dry — triangle
                # Intersection at y_int: z(y_int) = h_ws
                # z = z0 + dz_bed/dy * (y - y0)  → y_int = y0 + d0/(-dz_bed/dy + ...)
                # Simpler: wet fraction of dy = d0 / (d0 - d1)
                frac = d0 / (d0 - d1)
                dy_wet = frac * dy
                dz_wet = frac * dz_bed   # bed elevation change over wet part
                # Wet portion: from y0 (depth=d0) to y_int (depth=0)
                # Perimeter: slant from z0 to z_int = z0 + dz_wet
                P_total += np.sqrt(dy_wet**2 + dz_wet**2)
                A_total += 0.5 * d0 * dy_wet
                T_total += dy_wet

            else:  # d0 < 0, d1 > 0 — right wet, left dry
                frac = d1 / (d1 - d0)
                dy_wet = frac * dy
                dz_wet = (1.0 - frac) * dz_bed   # bed change from y_int to y1
                # Perimeter: slant from z_int = z1 - dz_wet to z1
                P_total += np.sqrt(dy_wet**2 + dz_wet**2)
                A_total += 0.5 * d1 * dy_wet
                T_total += dy_wet

        return A_total, P_total, T_total

    # ── Lookup interface ──────────────────────────────────────────────────

    def area(self, h_ws: float | np.ndarray) -> float | np.ndarray:
        """Cross-sectional area A [m²] at water surface elevation h_ws."""
        return np.interp(h_ws, self._h_table, self._A_table)

    def perimeter(self, h_ws: float | np.ndarray) -> float | np.ndarray:
        """Wetted perimeter P [m] at water surface elevation h_ws."""
        return np.interp(h_ws, self._h_table, self._P_table)

    def top_width(self, h_ws: float | np.ndarray) -> float | np.ndarray:
        """Top width T [m] at water surface elevation h_ws."""
        return np.interp(h_ws, self._h_table, self._T_table)

    def hydraulic_radius(self, h_ws: float | np.ndarray) -> float | np.ndarray:
        """Hydraulic radius R = A/P [m]."""
        A = self.area(h_ws)
        P = self.perimeter(h_ws)
        return np.where(P > 1e-9, A / P, 0.0)

    def h_from_area(self, A_target: float) -> float:
        """
        Inverse lookup: water surface elevation given cross-sectional area A.
        Uses linear interpolation on the lookup table.
        """
        if A_target <= 0:
            return self.z_min
        if A_target >= self._A_table[-1]:
            return self._h_table[-1]
        return float(np.interp(A_target, self._A_table, self._h_table))

    @classmethod
    def rectangular(
        cls,
        width: float,
        z_bed: float = 0.0,
        bank_height: float = 5.0,
        manning_n: float = 0.03,
    ) -> "CrossSection":
        """
        Create a simple rectangular cross-section (4 survey points).

        Vertical walls are approximated by steep slopes (ε = 0.1% of width).
        """
        bank_z = z_bed + bank_height
        eps = max(width * 0.001, 0.01)  # steep but not vertical walls
        return cls(
            y_points=np.array([0.0, eps, width - eps, width]),
            z_points=np.array([bank_z, z_bed, z_bed, bank_z]),
            manning_n=manning_n,
            bank_left_z=bank_z,
            bank_right_z=bank_z,
        )

    @classmethod
    def trapezoidal(
        cls,
        bottom_width: float,
        side_slope: float,   # horizontal : vertical
        z_bed: float = 0.0,
        bank_height: float = 5.0,
        manning_n: float = 0.03,
    ) -> "CrossSection":
        """Create a trapezoidal cross-section."""
        bank_z = z_bed + bank_height
        top_width = bottom_width + 2 * side_slope * bank_height
        return cls(
            y_points=np.array([0.0, side_slope * bank_height,
                                side_slope * bank_height + bottom_width,
                                top_width]),
            z_points=np.array([bank_z, z_bed, z_bed, bank_z]),
            manning_n=manning_n,
            bank_left_z=bank_z,
            bank_right_z=bank_z,
        )
