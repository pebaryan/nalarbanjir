"""
SimulationEngine — top-level orchestrator for all simulation modes.

Modes:
  '1d'   : Only the Preissmann 1D solver runs.
  '2d'   : Only the FV 2D solver runs.
  '1d2d' : Both solvers run; lateral exchange is computed at each step
           using the broad-crested weir formula (BankInterface + coupler).

Usage:
    engine = SimulationEngine(mode='1d2d', config=cfg)
    engine.initialize(network=my_network, interface=my_interface)
    for _ in range(1000):
        state = engine.step()

    # Or async:
    async for state in engine.run(steps=1000, yield_every=10):
        broadcast(state)
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import numpy as np

from src.core.config import NalarbanjirConfig, get_config
from src.core.exceptions import SolverNotInitializedError
from src.physics.state import (
    SimulationMode, SimulationState,
    Solver1DState, Solver2DState, CoupledState,
)
from src.physics.solver_1d.network import ChannelNetwork
from src.physics.solver_1d.preissmann import Solver1D
from src.physics.solver_2d.finite_volume import Solver2D
from src.physics.coupled.interface import BankInterface
from src.physics.coupled.coupler import (
    compute_exchange,
    apply_exchange_to_2d,
    apply_exchange_to_1d_Q,
)


class SimulationEngine:
    """
    Top-level simulation orchestrator.

    Wraps one or both physics solvers and handles their lateral coupling.
    Implements the AbstractSolver protocol so it can be used anywhere a
    solver is expected.
    """

    def __init__(
        self,
        mode: SimulationMode,
        config: NalarbanjirConfig | None = None,
    ) -> None:
        self._mode = mode
        self._cfg  = config or get_config()
        self._initialized = False

        self._solver_1d: Solver1D | None = None
        self._solver_2d: Solver2D | None = None
        self._interface: BankInterface | None = None
        self._exchange: np.ndarray = np.array([])

        self._t: float = 0.0

    # ── Setup ─────────────────────────────────────────────────────────────

    def initialize(
        self,
        network: ChannelNetwork | None = None,
        interface: BankInterface | None = None,
    ) -> None:
        """
        Initialize solver(s) and reset time to zero.

        Args:
            network:   Required for modes '1d' and '1d2d'.
            interface: Bank interface for mode '1d2d'.
                       If None, an empty interface (no exchange) is used.
        """
        if self._mode in ("1d", "1d2d"):
            if network is None:
                raise ValueError(
                    f"ChannelNetwork is required for mode '{self._mode}'"
                )
            self._solver_1d = Solver1D(network=network, config=self._cfg)
            self._solver_1d.initialize()

        if self._mode in ("2d", "1d2d"):
            self._solver_2d = Solver2D(config=self._cfg)
            self._solver_2d.initialize()

        if self._mode == "1d2d":
            self._interface = interface or BankInterface(points=[])
            self._exchange = np.zeros(self._interface.n_points)

        self._t = 0.0
        self._initialized = True

    # ── Time stepping ─────────────────────────────────────────────────────

    def step(self, dt: float | None = None) -> SimulationState:
        """Advance simulation by one engine step and return the new state."""
        if not self._initialized:
            raise SolverNotInitializedError("SimulationEngine")

        if self._mode == "1d":
            self._solver_1d.step(dt)
            self._t = self._solver_1d.current_time
            return self._solver_1d.state

        if self._mode == "2d":
            self._solver_2d.step()
            self._t = self._solver_2d.current_time
            return self._solver_2d.state

        return self._step_coupled(dt)

    def _step_coupled(self, dt: float | None) -> CoupledState:
        """Advance one coupled 1D+2D step with lateral bank exchange."""
        cc    = self._cfg.physics.coupling
        sc2   = self._cfg.physics.solver_2d
        iface = self._interface

        t_before = self._solver_1d.current_time

        # 1. Advance the 1D channel solver
        self._solver_1d.step(dt)
        dt_elapsed = self._solver_1d.current_time - t_before

        # 2. Compute exchange fluxes (if interface has points)
        if iface.n_points > 0:
            wse_1d = iface.extract_wse_1d(self._solver_1d.state)
            wse_2d = iface.extract_wse_2d(self._solver_2d.state)
            bank_z = iface.bank_elevations()

            self._exchange = compute_exchange(
                wse_1d=wse_1d,
                wse_2d=wse_2d,
                bank_elevations=bank_z,
                cell_width=sc2.dy,
                weir_coeff=cc.weir_coefficient,
            )

            i_arr = np.array([p.i for p in iface.points])
            j_arr = np.array([p.j for p in iface.points])
            n_arr = np.array([p.node_index for p in iface.points])

            # 3a. Add overflow volume to 2D cells
            apply_exchange_to_2d(
                self._solver_2d._h,
                self._exchange,
                i_arr, j_arr,
                dt_elapsed, sc2.dx, sc2.dy,
            )

            # 3b. Subtract overflow from 1D discharge
            apply_exchange_to_1d_Q(
                self._solver_1d._Q,
                self._exchange,
                n_arr,
            )

        # 4. Advance the 2D floodplain solver
        self._solver_2d.step()

        self._t = self._solver_1d.current_time

        return CoupledState(
            state_1d=self._solver_1d.state,
            state_2d=self._solver_2d.state,
            exchange_flux=self._exchange.copy(),
        )

    # ── Async interface ───────────────────────────────────────────────────

    async def run(
        self,
        steps: int,
        dt: float | None = None,
        yield_every: int = 1,
    ) -> AsyncIterator[SimulationState]:
        """
        Async generator: advance `steps` time steps, yielding state every
        `yield_every` steps.  Yields to the event loop between steps so the
        coroutine does not monopolise the thread.
        """
        if not self._initialized:
            raise SolverNotInitializedError("SimulationEngine")

        for i in range(steps):
            state = self.step(dt)
            if (i + 1) % yield_every == 0:
                yield state
            await asyncio.sleep(0)   # cooperative yield

    # ── Protocol helpers ──────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all solvers to t=0 initial conditions."""
        if self._solver_1d is not None:
            self._solver_1d.reset()
        if self._solver_2d is not None:
            self._solver_2d.reset()
        if len(self._exchange):
            self._exchange = np.zeros_like(self._exchange)
        self._t = 0.0

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    @property
    def state(self) -> SimulationState:
        if not self._initialized:
            raise SolverNotInitializedError("SimulationEngine")
        if self._mode == "1d":
            return self._solver_1d.state
        if self._mode == "2d":
            return self._solver_2d.state
        return CoupledState(
            state_1d=self._solver_1d.state,
            state_2d=self._solver_2d.state,
            exchange_flux=self._exchange.copy(),
        )

    @property
    def current_time(self) -> float:
        return self._t

    @property
    def mode(self) -> SimulationMode:
        return self._mode
