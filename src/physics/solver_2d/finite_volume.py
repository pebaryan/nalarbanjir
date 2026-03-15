"""
2D Finite-Volume Shallow Water Equation Solver.

Replaces the legacy shallow_water.py (np.gradient approach).

Numerical method:
  - Godunov-type finite volume with HLLE Riemann solver
  - MUSCL-minmod 2nd-order reconstruction
  - Operator splitting: hyperbolic step + source terms
  - CFL-adaptive explicit time stepping
  - Hydrostatic reconstruction for well-balanced bed slope
  - Pointwise implicit friction update (stable for large Manning n)
  - Proper wet/dry treatment (no negative depths)

Implements AbstractSolver protocol from src.physics.base.
"""
from __future__ import annotations

import numpy as np

from src.core.config import NalarbanjirConfig, get_config
from src.core.exceptions import SolverDivergedError, SolverNotInitializedError
from src.physics.state import Solver2DState
from src.physics.solver_2d.riemann import hlle_flux_x, hlle_flux_y
from src.physics.solver_2d.reconstruction import reconstruct_pair_x, reconstruct_pair_y
from src.physics.solver_2d.wet_dry import apply_wet_dry, extract_velocities, compute_cfl_dt
from src.physics.solver_2d.boundary import BoundaryConditions, apply_boundary_conditions

_GRAVITY = 9.81


class Solver2D:
    """
    2D finite-volume shallow water solver.

    Usage:
        cfg = get_config()
        solver = Solver2D(cfg)
        solver.initialize()
        for step in range(1000):
            solver.step()
        state = solver.state
    """

    def __init__(
        self,
        config: NalarbanjirConfig | None = None,
        bc: BoundaryConditions | None = None,
    ) -> None:
        self._cfg = config or get_config()
        self._sc  = self._cfg.physics.solver_2d
        self._tc  = self._cfg.terrain

        self.nx  = self._sc.nx
        self.ny  = self._sc.ny
        self.dx  = self._sc.dx
        self.dy  = self._sc.dy
        self.cfl = self._sc.cfl
        self.min_depth = self._sc.min_depth

        self.bc: BoundaryConditions = bc or BoundaryConditions()

        # Solution arrays — allocated in initialize()
        self._h:  np.ndarray | None = None
        self._hu: np.ndarray | None = None
        self._hv: np.ndarray | None = None
        self._z:  np.ndarray | None = None   # bed elevation (constant)
        self._n:  np.ndarray | None = None   # Manning n grid
        self._rain: np.ndarray | None = None # current rainfall rate [m/s]

        self._t: float = 0.0
        self._dt: float = self._sc.dt
        self._step_count: int = 0
        self._initialized: bool = False

        # Accumulators for mass conservation diagnostics
        self._initial_volume: float = 0.0
        self._cumulative_rain_volume: float = 0.0

    # ── Setup ─────────────────────────────────────────────────────────────

    def initialize(
        self,
        bed_elevation: np.ndarray | None = None,
        manning_n: np.ndarray | None = None,
        initial_depth: np.ndarray | float | None = None,
    ) -> None:
        """
        Set up initial conditions and allocate arrays.

        Args:
            bed_elevation: Bed elevation z [m], shape (nx, ny).
                           If None, generates a synthetic terrain.
            manning_n:     Manning roughness grid, shape (nx, ny).
                           If None, uses default_manning_n from config.
            initial_depth: Initial water depth h [m]. Scalar or (nx, ny).
                           If None, uses terrain.initial_water_depth from config.
        """
        nx, ny = self.nx, self.ny

        # Bed elevation
        if bed_elevation is not None:
            assert bed_elevation.shape == (nx, ny), \
                f"bed_elevation shape {bed_elevation.shape} != ({nx},{ny})"
            self._z = bed_elevation.astype(float)
        else:
            self._z = self._make_synthetic_terrain()

        # Manning n
        if manning_n is not None:
            self._n = manning_n.astype(float)
        else:
            self._n = np.full((nx, ny), self._tc.manning_n.open_land)

        # Initial depth
        if initial_depth is None:
            h0 = self._tc.initial_water_depth
        elif np.isscalar(initial_depth):
            h0 = float(initial_depth)
        else:
            h0 = np.asarray(initial_depth, dtype=float)
        self._h  = np.full((nx, ny), h0) if np.isscalar(h0) else h0.copy()
        self._hu = np.zeros((nx, ny))
        self._hv = np.zeros((nx, ny))
        self._rain = np.zeros((nx, ny))

        self._initial_volume = float(np.sum(self._h[1:-1, 1:-1])) * self.dx * self.dy
        self._cumulative_rain_volume = 0.0
        self._t = 0.0
        self._step_count = 0
        self._initialized = True

    def _make_synthetic_terrain(self) -> np.ndarray:
        """Generate a simple sinusoidal terrain for testing."""
        x = np.arange(self.nx) * self.dx
        y = np.arange(self.ny) * self.dy
        xx, yy = np.meshgrid(x, y, indexing="ij")
        A = self._tc.amplitude
        L = self._tc.wavelength
        return A * (np.sin(2 * np.pi * xx / L) + np.cos(2 * np.pi * yy / L))

    # ── AbstractSolver protocol ───────────────────────────────────────────

    def step(self, dt: float | None = None) -> None:
        """Advance solution by one time step using the FV method."""
        if not self._initialized:
            raise SolverNotInitializedError("Solver2D")

        h, hu, hv, z, n = self._h, self._hu, self._hv, self._z, self._n
        rain = self._rain

        # 0. Apply boundary conditions
        u, v = extract_velocities(h, hu, hv, self.min_depth)
        h, u, v = apply_boundary_conditions(h, u, v, self.bc, self._t)
        hu = h * u
        hv = h * v

        # 1. Compute CFL-stable dt
        if dt is None:
            dt = compute_cfl_dt(h, u, v, self.dx, self.dy, self.cfl, self.min_depth)
            dt = min(dt, self._sc.dt)   # cap at configured maximum

        # 2. MUSCL reconstruction + HLLE fluxes in x
        h_L, u_L, v_L, h_R, u_R, v_R = reconstruct_pair_x(h, u, v, z, self.min_depth)
        fx_h, fx_hu, fx_hv = hlle_flux_x(h_L, u_L, v_L, h_R, u_R, v_R)

        # 3. MUSCL reconstruction + HLLE fluxes in y
        h_B, u_B, v_B, h_T, u_T, v_T = reconstruct_pair_y(h, u, v, z, self.min_depth)
        gy_h, gy_hu, gy_hv = hlle_flux_y(h_B, u_B, v_B, h_T, u_T, v_T)

        # 4. Conservative update (flux divergence)
        #    dU/dt = -(F_{i+1/2} - F_{i-1/2})/dx - (G_{j+1/2} - G_{j-1/2})/dy
        h_new  = h[1:-1, 1:-1]  \
                 - (dt/self.dx) * (fx_h[1:, 1:-1]  - fx_h[:-1, 1:-1])  \
                 - (dt/self.dy) * (gy_h[1:-1, 1:]  - gy_h[1:-1, :-1])

        hu_new = hu[1:-1, 1:-1] \
                 - (dt/self.dx) * (fx_hu[1:, 1:-1] - fx_hu[:-1, 1:-1]) \
                 - (dt/self.dy) * (gy_hu[1:-1, 1:] - gy_hu[1:-1, :-1])

        hv_new = hv[1:-1, 1:-1] \
                 - (dt/self.dx) * (fx_hv[1:, 1:-1] - fx_hv[:-1, 1:-1]) \
                 - (dt/self.dy) * (gy_hv[1:-1, 1:] - gy_hv[1:-1, :-1])

        # 5. Bed slope source term (hydrostatic, well-balanced)
        #    S_bx = -g·h·∂z/∂x  ≈  -g·h_{i} · (z_{i+1} - z_{i-1})/(2dx)
        z_int = z[1:-1, 1:-1]
        h_int = h[1:-1, 1:-1]
        dzdx = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2 * self.dx)
        dzdy = (z[1:-1, 2:] - z[1:-1, :-2]) / (2 * self.dy)
        hu_new -= dt * _GRAVITY * h_int * dzdx
        hv_new -= dt * _GRAVITY * h_int * dzdy

        # 6. Rainfall source (continuity only)
        rain_int = rain[1:-1, 1:-1]
        h_new += dt * rain_int
        self._cumulative_rain_volume += float(np.sum(rain_int)) * self.dx * self.dy * dt

        # 7. Pointwise implicit friction (Manning)
        #    Implicit: hu^{n+1} = hu_new / (1 + dt·cf)
        #    cf = g·n²·|u| / h^(4/3)
        n_int = n[1:-1, 1:-1]
        u_new, v_new = extract_velocities(h_new, hu_new, hv_new, self.min_depth)
        speed_new = np.sqrt(u_new**2 + v_new**2)
        h_safe = np.maximum(h_new, self.min_depth)
        cf = _GRAVITY * n_int**2 * speed_new / h_safe**(4/3)
        denom = 1.0 + dt * cf
        hu_new /= denom
        hv_new /= denom

        # 8. Write back to interior (boundaries handled by BC applicator next step)
        h[1:-1, 1:-1]  = h_new
        hu[1:-1, 1:-1] = hu_new
        hv[1:-1, 1:-1] = hv_new

        # 9. Wet/dry enforcement
        self._h, self._hu, self._hv = apply_wet_dry(h, hu, hv, self.min_depth)

        # 10. Divergence check
        if not np.all(np.isfinite(self._h)):
            raise SolverDivergedError("Solver2D", self._step_count, "NaN/inf in water depth")

        self._dt = dt
        self._t += dt
        self._step_count += 1

    def reset(self) -> None:
        """Reset to initial conditions."""
        self._initialized = False
        self._h = self._hu = self._hv = None
        self._t = 0.0
        self._step_count = 0
        self.initialize()   # re-run with same terrain/n

    def pause(self) -> None:
        pass  # stateless solver, nothing to pause

    def resume(self) -> None:
        pass

    # ── State accessors ───────────────────────────────────────────────────

    @property
    def state(self) -> Solver2DState:
        if not self._initialized:
            raise SolverNotInitializedError("Solver2D")
        u, v = extract_velocities(self._h, self._hu, self._hv, self.min_depth)
        risk = self._compute_flood_risk(self._h)
        return Solver2DState(
            water_depth=self._h.copy(),
            velocity_x=u,
            velocity_y=v,
            bed_elevation=self._z.copy(),
            rainfall_rate=self._rain.copy(),
            flood_risk=risk,
        )

    @property
    def current_time(self) -> float:
        return self._t

    @property
    def dt(self) -> float:
        return self._dt

    def set_rainfall(self, rain: np.ndarray) -> None:
        """Update the rainfall source term. Call before each step for time-varying rain."""
        assert rain.shape == (self.nx, self.ny)
        self._rain = rain

    # ── Diagnostics ───────────────────────────────────────────────────────

    def mass_conservation_error(self) -> float:
        """
        Relative mass error over interior cells (excludes BC ghost-row effects).

        = |V_current_interior - (V_initial_interior + V_rain)| / V_initial_interior

        Boundary cells are excluded because reflective BCs mirror interior values
        into boundary rows each step, which introduces a small bookkeeping offset
        that is not a physical mass leak.
        """
        if not self._initialized:
            return 0.0
        h_int = self._h[1:-1, 1:-1]
        v_current = float(np.sum(h_int)) * self.dx * self.dy
        v_expected = self._initial_volume + self._cumulative_rain_volume
        if abs(v_expected) < 1e-9:
            return 0.0
        return abs(v_current - v_expected) / abs(v_expected)

    def _initial_interior_volume(self) -> float:
        """Volume over interior cells at t=0, for mass conservation tracking."""
        return float(np.sum(self._h[1:-1, 1:-1])) * self.dx * self.dy

    def _compute_flood_risk(self, h: np.ndarray) -> np.ndarray:
        """Map water depth to flood risk integer 0–4."""
        t = self._tc.flood_thresholds
        risk = np.zeros(h.shape, dtype=np.int8)
        risk[h >= t.minor]    = 1
        risk[h >= t.moderate] = 2
        risk[h >= t.major]    = 3
        risk[h >= t.severe]   = 4
        return risk
