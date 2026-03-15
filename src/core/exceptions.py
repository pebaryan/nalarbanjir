"""
Domain exceptions for Nalarbanjir.

All application-specific errors inherit from NalarbanjirError so callers
can catch the base class when they don't need to distinguish subtypes.
"""
from __future__ import annotations


class NalarbanjirError(Exception):
    """Base exception for all Nalarbanjir domain errors."""


# ── Solver exceptions ─────────────────────────────────────────────────────


class SolverDivergedError(NalarbanjirError):
    """Raised when a numerical solver produces NaN/inf or violates stability bounds."""

    def __init__(self, solver: str, step: int, reason: str = "") -> None:
        self.solver = solver
        self.step = step
        msg = f"Solver '{solver}' diverged at step {step}."
        if reason:
            msg += f" {reason}"
        super().__init__(msg)


class SolverNotInitializedError(NalarbanjirError):
    """Raised when a solver method is called before initialize()."""

    def __init__(self, solver: str) -> None:
        super().__init__(f"Solver '{solver}' has not been initialized. Call initialize() first.")


class SolverConfigError(NalarbanjirError):
    """Raised when solver parameters are physically or numerically invalid."""

    def __init__(self, solver: str, reason: str) -> None:
        super().__init__(f"Solver '{solver}' configuration error: {reason}")


# ── Config exceptions ─────────────────────────────────────────────────────


class InvalidConfigError(NalarbanjirError):
    """Raised for invalid or missing configuration values."""

    def __init__(self, field: str, value: object = None, reason: str = "") -> None:
        msg = f"Invalid config field '{field}'"
        if value is not None:
            msg += f" = {value!r}"
        if reason:
            msg += f". {reason}"
        super().__init__(msg)


# ── GIS exceptions ────────────────────────────────────────────────────────


class GISImportError(NalarbanjirError):
    """Raised when a GIS file cannot be imported or processed."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        msg = f"Failed to import GIS file '{path}'."
        if reason:
            msg += f" {reason}"
        super().__init__(msg)


class MeshGenerationError(NalarbanjirError):
    """Raised when 3D mesh generation from terrain data fails."""


class UnsupportedFormatError(NalarbanjirError):
    """Raised when an unsupported file format is encountered."""

    def __init__(self, fmt: str, supported: list[str] | None = None) -> None:
        msg = f"Unsupported format '{fmt}'."
        if supported:
            msg += f" Supported: {supported}"
        super().__init__(msg)


# ── ML exceptions ─────────────────────────────────────────────────────────


class MLModelError(NalarbanjirError):
    """Raised when the ML model encounters an error during inference or training."""


class MLCheckpointNotFoundError(MLModelError):
    """Raised when a model checkpoint file does not exist."""

    def __init__(self, path: str) -> None:
        super().__init__(f"ML checkpoint not found: '{path}'")


# ── Simulation exceptions ─────────────────────────────────────────────────


class SimulationStateError(NalarbanjirError):
    """Raised when the simulation state is invalid or inconsistent."""


class SimulationAlreadyRunningError(NalarbanjirError):
    """Raised when a run is requested while another is already active."""

    def __init__(self) -> None:
        super().__init__("A simulation is already running. Reset or wait for completion.")


# ── Coupling exceptions ───────────────────────────────────────────────────


class CouplingError(NalarbanjirError):
    """Raised when 1D-2D coupling fails (e.g., incompatible grids)."""

    def __init__(self, reason: str = "") -> None:
        msg = "1D-2D coupling error."
        if reason:
            msg += f" {reason}"
        super().__init__(msg)
