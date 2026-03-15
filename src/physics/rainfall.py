"""
Rainfall source term generator for the 2D shallow water solver.

Rainfall appears as a source term in the continuity equation:
    ∂h/∂t + ... = R(x, y, t) - I(x, y, t)
where R is rainfall rate [m/s] and I is infiltration rate [m/s].

Supported spatial patterns:
  - uniform:    constant intensity over the entire domain
  - storm_cell: Gaussian distribution peaked at storm center
  - frontal:    linear gradient across the domain (weather front)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

RainfallType = Literal["uniform", "storm_cell", "frontal"]


@dataclass
class RainfallEvent:
    """Describes a single rainfall event."""
    pattern: RainfallType = "uniform"
    intensity: float = 0.0          # Peak intensity [m/s]
    duration: float = 3600.0        # Duration [s]
    start_time: float = 0.0         # Start time [s]

    # Storm cell parameters
    storm_x: float = 5000.0         # Storm center x [m]
    storm_y: float = 5000.0         # Storm center y [m]
    sigma: float = 2000.0           # Gaussian spread [m]

    # Frontal parameters
    front_direction: float = 0.0    # Angle of front normal [radians]
    front_width: float = 3000.0     # Width of transition zone [m]


class RainfallGenerator:
    """
    Generates spatially distributed rainfall arrays for a given domain.

    Args:
        nx, ny: Grid dimensions
        dx, dy: Cell sizes [m]
        domain_x, domain_y: Domain origin offset [m] (default 0)
    """

    def __init__(
        self,
        nx: int,
        ny: int,
        dx: float,
        dy: float,
        domain_x: float = 0.0,
        domain_y: float = 0.0,
    ) -> None:
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy

        # Cell-centre coordinates
        self.x = np.arange(nx) * dx + dx * 0.5 + domain_x   # shape (nx,)
        self.y = np.arange(ny) * dy + dy * 0.5 + domain_y   # shape (ny,)
        self.xx, self.yy = np.meshgrid(self.x, self.y, indexing="ij")  # (nx, ny)

    def get_rate(self, event: RainfallEvent, t: float) -> np.ndarray:
        """
        Compute rainfall rate [m/s] at time t for the given event.

        Returns zero array if t is outside [start_time, start_time + duration].

        Args:
            event: RainfallEvent specification
            t:     Current simulation time [s]

        Returns:
            rain: Rainfall rate array, shape (nx, ny), [m/s]
        """
        t_local = t - event.start_time
        if t_local < 0 or t_local > event.duration or event.intensity <= 0:
            return np.zeros((self.nx, self.ny))

        if event.pattern == "uniform":
            return self._uniform(event)
        elif event.pattern == "storm_cell":
            return self._storm_cell(event)
        elif event.pattern == "frontal":
            return self._frontal(event)
        return np.zeros((self.nx, self.ny))

    def _uniform(self, event: RainfallEvent) -> np.ndarray:
        return np.full((self.nx, self.ny), event.intensity)

    def _storm_cell(self, event: RainfallEvent) -> np.ndarray:
        """Gaussian storm cell centred at (storm_x, storm_y)."""
        r2 = (self.xx - event.storm_x)**2 + (self.yy - event.storm_y)**2
        return event.intensity * np.exp(-r2 / (2 * event.sigma**2))

    def _frontal(self, event: RainfallEvent) -> np.ndarray:
        """
        Linear weather front: intensity varies from 0 to peak across the domain.
        front_direction defines the direction of increasing intensity.
        """
        cos_a = np.cos(event.front_direction)
        sin_a = np.sin(event.front_direction)
        # Projection of position onto front normal
        proj = self.xx * cos_a + self.yy * sin_a
        proj_min, proj_max = proj.min(), proj.max()
        proj_range = max(proj_max - proj_min, 1.0)
        normalized = (proj - proj_min) / proj_range
        return event.intensity * np.clip(normalized, 0.0, 1.0)
