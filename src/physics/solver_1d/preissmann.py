"""
Preissmann θ-implicit scheme for the 1D Saint-Venant equations.

Solves:
    ∂A/∂t + ∂Q/∂x = q_l                                         (continuity)
    ∂Q/∂t + ∂(αQ²/A)/∂x + gA·∂h/∂x + gA(S_f - S_0) = 0         (momentum)

where:
    A  = cross-sectional area [m²]
    Q  = discharge [m³/s]
    h  = water surface elevation [m a.s.l.]
    q_l = lateral inflow per unit length [m²/s] (set to 0 for now)
    α  = Boussinesq coefficient (≈1 for fully turbulent flow)
    S_f = friction slope = n²·Q|Q| / (A²·R^(4/3))   [Manning]
    S_0 = bed slope [m/m]

Discretization (Preissmann, θ=0.6):
    Any value f at (x_{i+1/2}, t^{n+θ}) is:
        f ≈ θ/2·(f_i^{n+1} + f_{i+1}^{n+1}) + (1-θ)/2·(f_i^n + f_{i+1}^n)

This yields a block-tridiagonal linear system (2×2 blocks per node) solved
with the Thomas double-sweep algorithm in O(N) operations.

For a single reach with N+1 nodes (1 upstream boundary + N-1 interior + 1 downstream):
    System size: 2(N+1) equations
    Structure: tridiagonal in 2×2 blocks → Thomas algorithm
"""
from __future__ import annotations

import numpy as np

from src.core.config import NalarbanjirConfig, get_config
from src.core.exceptions import SolverDivergedError, SolverNotInitializedError
from src.physics.state import Solver1DState
from src.physics.solver_1d.network import ChannelNetwork, NodeType, BCType1D
from src.physics.solver_1d.boundary import apply_boundary_conditions

_GRAVITY = 9.81
_ALPHA   = 1.0   # Boussinesq coefficient


class Solver1D:
    """
    Preissmann implicit 1D Saint-Venant solver.

    Works on a single straight reach (most common case). Junction handling
    for bifurcating networks is done by the CoupledSolver.

    Usage:
        network = ChannelNetwork.simple_reach(...)
        solver = Solver1D(network, config)
        solver.initialize()
        for _ in range(1000):
            solver.step()
        state = solver.state
    """

    def __init__(
        self,
        network: ChannelNetwork,
        config: NalarbanjirConfig | None = None,
    ) -> None:
        self._network = network
        self._cfg = config or get_config()
        sc = self._cfg.physics.solver_1d

        self.theta          = sc.theta
        self._dt_value      = sc.dt
        self.tolerance      = sc.tolerance
        self.max_iterations = sc.max_iterations

        # Node ordering (single reach assumption)
        reaches = list(network.edges.values())
        assert len(reaches) == 1, "Solver1D currently supports single-reach networks"
        reach = reaches[0]
        self._node_ids: list[str] = reach.node_ids
        self._n_nodes = len(self._node_ids)
        self._reach = reach

        # Solution arrays — allocated in initialize()
        self._h: np.ndarray | None = None   # water surface elevation [m a.s.l.]
        self._Q: np.ndarray | None = None   # discharge [m³/s]
        self._A: np.ndarray | None = None   # cross-sectional area [m²]

        self._t: float = 0.0
        self._step_count: int = 0
        self._initialized: bool = False

    # ── Setup ─────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Set initial conditions: steady uniform flow as a first estimate."""
        n = self._n_nodes
        self._h = np.zeros(n)
        self._Q = np.zeros(n)
        self._A = np.zeros(n)

        # Get downstream stage BC as initial water surface
        nodes = [self._network.get_node(nid) for nid in self._node_ids]
        down_node = nodes[-1]
        if (down_node.boundary_condition is not None
                and down_node.boundary_condition.bc_type == BCType1D.STAGE):
            h_ds = down_node.boundary_condition.get_value(0.0)
        else:
            h_ds = 2.0   # fallback

        # Get upstream discharge
        up_node = nodes[0]
        if (up_node.boundary_condition is not None
                and up_node.boundary_condition.bc_type == BCType1D.DISCHARGE):
            Q_us = up_node.boundary_condition.get_value(0.0)
        else:
            Q_us = 10.0

        # Linear water surface slope + uniform Q as initial guess
        h_us = h_ds + self._reach.slope * self._reach.length
        chainage = np.array([nd.chainage for nd in nodes])
        x_norm = chainage / max(chainage[-1], 1.0)
        self._h = h_ds + (h_us - h_ds) * (1.0 - x_norm)
        self._Q = np.full(n, Q_us)

        # Compute initial areas from h
        for i, nid in enumerate(self._node_ids):
            node = self._network.get_node(nid)
            if node.cross_section is not None:
                self._A[i] = float(node.cross_section.area(self._h[i]))
            else:
                self._A[i] = 1.0   # boundary node placeholder

        self._t = 0.0
        self._step_count = 0
        self._initialized = True

    # ── Solver core ───────────────────────────────────────────────────────

    def step(self, dt: float | None = None) -> None:
        """Advance the 1D solution by one time step using Preissmann scheme."""
        if not self._initialized:
            raise SolverNotInitializedError("Solver1D")

        dt = dt or self.dt
        theta = self.theta
        n = self._n_nodes

        h_old = self._h.copy()
        Q_old = self._Q.copy()
        A_old = self._A.copy()

        nodes = [self._network.get_node(nid) for nid in self._node_ids]
        chainage = np.array([nd.chainage for nd in nodes])
        dx = np.diff(chainage)   # spacing between consecutive nodes

        # Newton-Raphson iteration (1 iteration for linear problem is usually enough)
        h_new = h_old.copy()
        Q_new = Q_old.copy()

        for _iter in range(self.max_iterations):
            A_new = np.array([
                float(nodes[i].cross_section.area(h_new[i]))
                if nodes[i].cross_section is not None else A_old[i]
                for i in range(n)
            ])
            T_new = np.array([
                float(nodes[i].cross_section.top_width(h_new[i]))
                if nodes[i].cross_section is not None else 1.0
                for i in range(n)
            ])
            R_new = np.array([
                float(nodes[i].cross_section.hydraulic_radius(h_new[i]))
                if nodes[i].cross_section is not None else 1.0
                for i in range(n)
            ])
            n_man = np.array([
                nodes[i].cross_section.manning_n
                if nodes[i].cross_section is not None
                else self._cfg.physics.solver_1d.default_manning_n
                for i in range(n)
            ])

            # ── Assemble 2n × 2n system ──────────────────────────────────────────
            # x = [h_0, Q_0, h_1, Q_1, ..., h_{n-1}, Q_{n-1}]
            #
            # Row layout (n nodes, n-1 intervals):
            #   Row 0:           upstream BC  (Q_0 or h_0)
            #   Rows 2k+1, 2k+2: continuity + momentum for interval k (k=0..n-2)
            #   Row 2n-1:        downstream BC (h_{n-1} or Q_{n-1})
            #
            size = 2 * n
            mat = np.zeros((size, size))
            rhs = np.zeros(size)

            # ── Upstream BC (row 0) ──
            up_bc = nodes[0].boundary_condition
            if up_bc is not None and up_bc.bc_type == BCType1D.DISCHARGE:
                Q_bc = up_bc.get_value(self._t + dt)
                mat[0, 1] = 1.0        # Q[0] = Q_bc
                rhs[0] = Q_bc
            else:
                mat[0, 0] = 1.0        # h[0] = h_old[0]
                rhs[0] = h_old[0]

            # ── Downstream BC (row 2n-1) ──
            down_bc = nodes[-1].boundary_condition
            if down_bc is not None and down_bc.bc_type == BCType1D.STAGE:
                h_bc = down_bc.get_value(self._t + dt)
                mat[size - 1, 2*(n-1)] = 1.0   # h[n-1] = h_bc
                rhs[size - 1] = h_bc
            else:
                mat[size - 1, 2*(n-1) + 1] = 1.0  # Q[n-1] = Q_old[-1]
                rhs[size - 1] = Q_old[-1]

            # ── Interior equations: one pair per interval k = 0..n-2 ──
            for k in range(n - 1):
                row_c = 2 * k + 1   # continuity for interval [k, k+1]
                row_m = 2 * k + 2   # momentum   for interval [k, k+1]

                i0, i1 = k, k + 1
                dx_k = dx[k]
                S0_k = self._reach.slope

                A_av  = max(0.5 * (A_new[i0] + A_new[i1]), 0.01)
                A_av0 = max(0.5 * (A_old[i0] + A_old[i1]), 0.01)
                T_av  = max(0.5 * (T_new[i0] + T_new[i1]), 0.1)
                R_av  = max(0.5 * (R_new[i0] + R_new[i1]), 0.01)
                n_av  = 0.5 * (n_man[i0] + n_man[i1])

                Q_av  = 0.5 * (Q_new[i0] + Q_new[i1])
                Sf_av = (n_av**2 * Q_av * abs(Q_av)) / max(A_av**2 * R_av**(4/3), 1e-9)

                # Continuity (linearised, A ≈ T·h):
                #   T/2dt·(h_i + h_{i+1}) + θ/dx·(Q_{i+1} - Q_i) = RHS_c
                T_2dt = T_av / (2.0 * dt)
                th_dx = _ALPHA * theta / dx_k

                mat[row_c, 2*i0]   =  T_2dt    # h_i
                mat[row_c, 2*i0+1] = -th_dx    # Q_i
                mat[row_c, 2*i1]   =  T_2dt    # h_{i+1}
                mat[row_c, 2*i1+1] =  th_dx    # Q_{i+1}
                rhs[row_c] = (T_2dt * (h_old[i0] + h_old[i1])
                              - _ALPHA * (1 - theta) / dx_k * (Q_old[i1] - Q_old[i0]))

                # Momentum (linearised):
                #   0.5/dt·(Q_i + Q_{i+1}) + θ·gA/dx·(h_{i+1} - h_i) = RHS_m
                half_dt = 0.5 / dt
                beta    = _GRAVITY * A_av * theta / dx_k

                mat[row_m, 2*i0]   = -beta      # h_i
                mat[row_m, 2*i0+1] =  half_dt   # Q_i
                mat[row_m, 2*i1]   =  beta       # h_{i+1}
                mat[row_m, 2*i1+1] =  half_dt   # Q_{i+1}
                rhs[row_m] = (half_dt * (Q_old[i0] + Q_old[i1])
                              - _GRAVITY * A_av0 * (1 - theta) / dx_k
                                * (h_old[i1] - h_old[i0])
                              - _GRAVITY * A_av * (Sf_av - S0_k))

            # ── Solve ──
            try:
                x = np.linalg.solve(mat, rhs)
            except np.linalg.LinAlgError as e:
                raise SolverDivergedError("Solver1D", self._step_count, str(e))

            h_next = x[0::2]
            Q_next = x[1::2]

            # Check convergence
            dh = np.max(np.abs(h_next - h_new))
            dQ = np.max(np.abs(Q_next - Q_new))
            h_new = h_next.copy()
            Q_new = Q_next.copy()
            if dh < self.tolerance and dQ < self.tolerance:
                break

        # Divergence check
        if not np.all(np.isfinite(h_new)) or not np.all(np.isfinite(Q_new)):
            raise SolverDivergedError("Solver1D", self._step_count,
                                       "NaN/inf in h or Q")

        # Update state
        self._h = h_new
        self._Q = Q_new
        self._A = np.array([
            float(nodes[i].cross_section.area(h_new[i]))
            if nodes[i].cross_section is not None else self._A[i]
            for i in range(n)
        ])
        self._t += dt
        self._step_count += 1

    # ── AbstractSolver protocol ───────────────────────────────────────────

    def reset(self) -> None:
        self._initialized = False
        self.initialize()

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    @property
    def state(self) -> Solver1DState:
        if not self._initialized:
            raise SolverNotInitializedError("Solver1D")
        nodes = [self._network.get_node(nid) for nid in self._node_ids]
        chainage = np.array([nd.chainage for nd in nodes])
        V = np.where(self._A > 1e-9, self._Q / self._A, 0.0)
        return Solver1DState(
            chainage=chainage,
            discharge=self._Q.copy(),
            water_surface_elev=self._h.copy(),
            area=self._A.copy(),
            velocity=V,
            node_ids=list(self._node_ids),
        )

    @property
    def current_time(self) -> float:
        return self._t

    @property
    def dt(self) -> float:
        return self._dt_value

    @dt.setter
    def dt(self, value: float) -> None:
        self._dt_value = value
