"""
AbstractSolver protocol — the interface all three hydraulic solvers must satisfy.

Any class that implements step(), reset(), initialize(), state, and current_time
satisfies this protocol without explicit inheritance (structural subtyping).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

# Forward reference — avoids circular import; state module imports nothing from here
from src.physics.state import SimulationState


@runtime_checkable
class AbstractSolver(Protocol):
    """
    Structural protocol for hydraulic solvers.

    Implementations: Solver2D (finite-volume), Solver1D (Preissmann), CoupledSolver.
    All three are interchangeable from the SimulationEngine's perspective.
    """

    def initialize(self) -> None:
        """
        Set up initial conditions and allocate arrays.
        Must be called once before the first step().
        """
        ...

    def step(self, dt: float | None = None) -> None:
        """
        Advance the solution by one time step.

        Args:
            dt: Override time step [s]. If None, use the solver's internal dt
                (which may be CFL-adaptive for the 2D solver).
        """
        ...

    def reset(self) -> None:
        """Return solver to its initial state (t=0, initial conditions)."""
        ...

    def pause(self) -> None:
        """
        Pause time-stepping. Default no-op — override if the solver needs
        to quiesce background threads or release resources during pause.
        """

    def resume(self) -> None:
        """Resume after pause(). Default no-op."""

    @property
    def state(self) -> SimulationState:
        """
        Current solver state snapshot.

        Returns a Solver1DState, Solver2DState, or CoupledState depending
        on the solver type. The engine serializes this for WebSocket broadcast.
        """
        ...

    @property
    def current_time(self) -> float:
        """Elapsed simulation time in seconds since initialize()."""
        ...

    @property
    def dt(self) -> float:
        """Current time step [s] (may change each step for CFL-adaptive solvers)."""
        ...
