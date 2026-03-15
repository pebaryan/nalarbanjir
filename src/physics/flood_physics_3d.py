"""3D Flood Physics Engine for flood simulation.

This module implements the shallow water equations (Saint-Venant equations)
in 3D with support for complex terrain and realistic flood propagation.
"""

import logging
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from scipy.ndimage import sobel

logger = logging.getLogger(__name__)


@dataclass
class FloodState:
    """Current state of the flood simulation.

    Attributes:
        water_depth: 2D array of water depth at each grid point
        velocity_u: 2D array of x-component velocity (m/s)
        velocity_v: 2D array of y-component velocity (m/s)
        time: Current simulation time in seconds
    """

    water_depth: np.ndarray
    velocity_u: np.ndarray
    velocity_v: np.ndarray
    time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "water_depth": self.water_depth.tolist(),
            "velocity_u": self.velocity_u.tolist(),
            "velocity_v": self.velocity_v.tolist(),
            "time": self.time,
        }


class FloodPhysicsEngine3D:
    """3D Flood physics engine using shallow water equations.

    Solves the 2D shallow water equations (depth-averaged) on a structured grid:
    - Continuity equation: ∂h/∂t + ∂(hu)/∂x + ∂(hv)/∂y = S (source term)
    - Momentum x: ∂(hu)/∂t + ∂(hu² + ½gh²)/∂x + ∂(huv)/∂y = -gh ∂z/∂x - Cf|u|u
    - Momentum y: ∂(hv)/∂t + ∂(huv)/∂x + ∂(hv² + ½gh²)/∂y = -gh ∂z/∂y - Cf|v|v

    Where:
    - h: water depth
    - u, v: depth-averaged velocities in x and y
    - g: gravitational acceleration
    - z: bed elevation
    - Cf: friction coefficient

    Example:
        >>> engine = FloodPhysicsEngine3D(grid_size=(100, 100), dx=10.0)
        >>> engine.set_terrain(elevation_data)
        >>> engine.add_initial_water_source(x=50, y=50, depth=5.0, radius=10)
        >>> for i in range(100):
        ...     state = engine.step(dt=0.1)
    """

    def __init__(
        self,
        grid_size: Tuple[int, int],
        dx: float = 10.0,
        dy: Optional[float] = None,
        gravity: float = 9.81,
        manning_n: float = 0.03,
    ):
        """Initialize flood physics engine.

        Args:
            grid_size: Grid dimensions (nx, ny)
            dx: Grid spacing in x direction (meters)
            dy: Grid spacing in y direction (meters), defaults to dx
            gravity: Gravitational acceleration (m/s²)
            manning_n: Manning's roughness coefficient
        """
        self.nx, self.ny = grid_size
        self.dx = dx
        self.dy = dy or dx
        self.g = gravity
        self.manning_n = manning_n

        # Initialize state arrays
        self.h = np.zeros((self.nx, self.ny))  # Water depth
        self.u = np.zeros((self.nx, self.ny))  # X-velocity
        self.v = np.zeros((self.nx, self.ny))  # Y-velocity

        # Terrain elevation
        self.z = np.zeros((self.nx, self.ny))  # Bed elevation
        self.z_x = np.zeros((self.nx, self.ny))  # Bed slope x
        self.z_y = np.zeros((self.nx, self.ny))  # Bed slope y

        # Time
        self.time = 0.0
        self.timestep = 0

        # Source terms
        self.rainfall_source = np.zeros((self.nx, self.ny))
        self.inflow_sources: List[Dict] = []

        # Boundary conditions
        self.boundary_type = "wall"  # wall, open, periodic

        logger.info(
            f"FloodPhysicsEngine3D initialized: {self.nx}x{self.ny} grid, dx={self.dx}m"
        )

    def set_terrain(self, elevation: np.ndarray):
        """Set terrain elevation data.

        Args:
            elevation: 2D array of bed elevation (meters)
        """
        if elevation.shape != (self.nx, self.ny):
            raise ValueError(
                f"Elevation shape {elevation.shape} doesn't match grid {(self.nx, self.ny)}"
            )

        self.z = elevation.copy()

        # Calculate bed slopes using Sobel operators
        self._calculate_slopes()

        logger.info(
            f"Terrain set: elevation range [{self.z.min():.2f}, {self.z.max():.2f}] m"
        )

    def _calculate_slopes(self):
        """Calculate bed slopes using central differences."""
        # Use Sobel operator for smoother gradients
        self.z_x = (
            sobel(self.z, axis=0) / (8 * self.dx)
            if self.nx > 2
            else np.zeros_like(self.z)
        )
        self.z_y = (
            sobel(self.z, axis=1) / (8 * self.dy)
            if self.ny > 2
            else np.zeros_like(self.z)
        )

        # Fallback to central differences at boundaries
        if self.nx > 2:
            self.z_x[1:-1, :] = (self.z[2:, :] - self.z[:-2, :]) / (2 * self.dx)
        if self.ny > 2:
            self.z_y[:, 1:-1] = (self.z[:, 2:] - self.z[:, :-2]) / (2 * self.dy)

    def add_initial_water_source(
        self, x: int, y: int, depth: float, radius: int = 5, shape: str = "circular"
    ):
        """Add initial water source.

        Args:
            x: X grid coordinate of center
            y: Y grid coordinate of center
            depth: Maximum water depth (m)
            radius: Radius in grid cells
            shape: "circular" or "rectangular"
        """
        x = np.clip(x, radius, self.nx - radius - 1)
        y = np.clip(y, radius, self.ny - radius - 1)

        if shape == "circular":
            # Circular source with Gaussian decay
            for i in range(max(0, x - radius), min(self.nx, x + radius + 1)):
                for j in range(max(0, y - radius), min(self.ny, y + radius + 1)):
                    dist = np.sqrt((i - x) ** 2 + (j - y) ** 2)
                    if dist <= radius:
                        # Gaussian distribution
                        if radius > 0:
                            h_add = depth * np.exp(-(dist**2) / (2 * (radius / 2) ** 2))
                        else:
                            h_add = depth  # Single cell, no decay
                        self.h[i, j] = max(self.h[i, j], h_add)

        elif shape == "rectangular":
            # Rectangular source
            x_min, x_max = max(0, x - radius), min(self.nx, x + radius + 1)
            y_min, y_max = max(0, y - radius), min(self.ny, y + radius + 1)
            self.h[x_min:x_max, y_min:y_max] = np.maximum(
                self.h[x_min:x_max, y_min:y_max], depth
            )

        logger.info(f"Added water source at ({x}, {y}) with depth {depth}m")

    def set_rainfall(self, rainfall_intensity: np.ndarray):
        """Set rainfall source term.

        Args:
            rainfall_intensity: 2D array of rainfall intensity (mm/hr)
        """
        # Convert mm/hr to m/s
        self.rainfall_source = rainfall_intensity / 1000.0 / 3600.0

        logger.info(
            f"Rainfall set: mean intensity {rainfall_intensity.mean():.2f} mm/hr"
        )

    def set_boundary_conditions(self, boundary_type: str):
        """Set boundary condition type.

        Args:
            boundary_type: "wall", "open", or "periodic"
        """
        self.boundary_type = boundary_type
        logger.info(f"Boundary conditions set to: {boundary_type}")

    def calculate_courant_timestep(self) -> float:
        """Calculate stable timestep using CFL condition.

        Returns:
            Maximum stable timestep in seconds
        """
        # Find maximum wave speed
        h_safe = np.maximum(self.h, 0.01)  # Avoid division by zero
        celerity = np.sqrt(self.g * h_safe)  # Wave celerity

        speed = np.sqrt(self.u**2 + self.v**2)
        max_speed = np.max(speed + celerity)

        # CFL condition: dt < min(dx, dy) / max_speed
        if max_speed > 0:
            dt = 0.4 * min(self.dx, self.dy) / max_speed
        else:
            dt = 1.0  # Default timestep

        # Limit timestep for stability
        return min(dt, 10.0)

    def step(self, dt: Optional[float] = None) -> FloodState:
        """Advance simulation by one timestep.

        Args:
            dt: Timestep in seconds (calculated automatically if None)

        Returns:
            Current flood state
        """
        # Calculate timestep if not provided
        if dt is None:
            dt = self.calculate_courant_timestep()

        # Apply boundary conditions
        self._apply_boundary_conditions()

        # Store old state
        h_old = self.h.copy()
        u_old = self.u.copy()
        v_old = self.v.copy()

        # Calculate fluxes using Lax-Friedrichs scheme
        self._update_continuity(dt, h_old)
        self._update_momentum_x(dt, h_old, u_old, v_old)
        self._update_momentum_y(dt, h_old, u_old, v_old)

        # Apply friction
        self._apply_friction(dt)

        # Ensure non-negative depth
        self.h = np.maximum(self.h, 0.0)

        # Update time
        self.time += dt
        self.timestep += 1

        return self.get_state()

    def _apply_boundary_conditions(self):
        """Apply boundary conditions to state arrays."""
        if self.boundary_type == "wall":
            # Reflective (wall) boundaries - zero flux
            self.h[0, :] = self.h[1, :]
            self.h[-1, :] = self.h[-2, :]
            self.h[:, 0] = self.h[:, 1]
            self.h[:, -1] = self.h[:, -2]

            self.u[0, :] = 0.0
            self.u[-1, :] = 0.0
            self.u[:, 0] = -self.u[:, 1]
            self.u[:, -1] = -self.u[:, -2]

            self.v[0, :] = -self.v[1, :]
            self.v[-1, :] = -self.v[-2, :]
            self.v[:, 0] = 0.0
            self.v[:, -1] = 0.0

        elif self.boundary_type == "open":
            # Open boundaries - zero gradient
            self.h[0, :] = self.h[1, :]
            self.h[-1, :] = self.h[-2, :]
            self.h[:, 0] = self.h[:, 1]
            self.h[:, -1] = self.h[:, -2]

            self.u[0, :] = self.u[1, :]
            self.u[-1, :] = self.u[-2, :]
            self.u[:, 0] = self.u[:, 1]
            self.u[:, -1] = self.u[:, -2]

            self.v[0, :] = self.v[1, :]
            self.v[-1, :] = self.v[-2, :]
            self.v[:, 0] = self.v[:, 1]
            self.v[:, -1] = self.v[:, -2]

    def _update_continuity(self, dt: float, h_old: np.ndarray):
        """Update continuity equation (mass conservation).

        ∂h/∂t + ∂(hu)/∂x + ∂(hv)/∂y = source
        """
        # Calculate fluxes
        hu = h_old * self.u
        hv = h_old * self.v

        # Spatial derivatives (central differences with upwinding)
        dhu_dx = np.zeros_like(h_old)
        dhv_dy = np.zeros_like(h_old)

        if self.nx > 2:
            dhu_dx[1:-1, :] = (hu[2:, :] - hu[:-2, :]) / (2 * self.dx)
        if self.ny > 2:
            dhv_dy[:, 1:-1] = (hv[:, 2:] - hv[:, :-2]) / (2 * self.dy)

        # Update water depth
        self.h = h_old - dt * (dhu_dx + dhv_dy)

        # Add rainfall source
        self.h += dt * self.rainfall_source

        # Add inflow sources
        for source in self.inflow_sources:
            x, y = source["x"], source["y"]
            rate = source["rate"]  # m³/s

            # Convert to depth change (assuming unit area)
            area = self.dx * self.dy
            self.h[x, y] += dt * rate / area

    def _update_momentum_x(
        self, dt: float, h_old: np.ndarray, u_old: np.ndarray, v_old: np.ndarray
    ):
        """Update x-momentum equation.

        ∂(hu)/∂t + ∂(hu² + ½gh²)/∂x + ∂(huv)/∂y = -gh ∂z/∂x
        """
        # Flux terms
        hu2 = h_old * u_old**2 + 0.5 * self.g * h_old**2
        huv = h_old * u_old * v_old

        # Spatial derivatives
        dhu2_dx = np.zeros_like(u_old)
        dhuv_dy = np.zeros_like(u_old)

        if self.nx > 2:
            dhu2_dx[1:-1, :] = (hu2[2:, :] - hu2[:-2, :]) / (2 * self.dx)
        if self.ny > 2:
            dhuv_dy[:, 1:-1] = (huv[:, 2:] - huv[:, :-2]) / (2 * self.dy)

        # Pressure gradient (bed slope)
        pressure_grad = self.g * h_old * self.z_x

        # Update momentum
        hu_new = h_old * u_old - dt * (dhu2_dx + dhuv_dy + pressure_grad)

        # Calculate new velocity (avoid division by zero)
        h_safe = np.maximum(self.h, 0.001)
        self.u = hu_new / h_safe

    def _update_momentum_y(
        self, dt: float, h_old: np.ndarray, u_old: np.ndarray, v_old: np.ndarray
    ):
        """Update y-momentum equation.

        ∂(hv)/∂t + ∂(huv)/∂x + ∂(hv² + ½gh²)/∂y = -gh ∂z/∂y
        """
        # Flux terms
        huv = h_old * u_old * v_old
        hv2 = h_old * v_old**2 + 0.5 * self.g * h_old**2

        # Spatial derivatives
        dhuv_dx = np.zeros_like(v_old)
        dhv2_dy = np.zeros_like(v_old)

        if self.nx > 2:
            dhuv_dx[1:-1, :] = (huv[2:, :] - huv[:-2, :]) / (2 * self.dx)
        if self.ny > 2:
            dhv2_dy[:, 1:-1] = (hv2[:, 2:] - hv2[:, :-2]) / (2 * self.dy)

        # Pressure gradient (bed slope)
        pressure_grad = self.g * h_old * self.z_y

        # Update momentum
        hv_new = h_old * v_old - dt * (dhuv_dx + dhv2_dy + pressure_grad)

        # Calculate new velocity (avoid division by zero)
        h_safe = np.maximum(self.h, 0.001)
        self.v = hv_new / h_safe

    def _apply_friction(self, dt: float):
        """Apply friction using Manning's equation."""
        # Manning's equation: u = (1/n) * R^(2/3) * S^(1/2)
        # Friction term: -g * n² * |u| * u / h^(1/3)

        h_safe = np.maximum(self.h, 0.01)
        speed = np.sqrt(self.u**2 + self.v**2)

        # Friction coefficient
        Cf = self.g * self.manning_n**2 / (h_safe ** (1 / 3))

        # Apply friction to velocity
        friction_factor = 1.0 / (1.0 + dt * Cf * speed)
        self.u *= friction_factor
        self.v *= friction_factor

    def get_state(self) -> FloodState:
        """Get current flood state.

        Returns:
            FloodState object with current simulation state
        """
        return FloodState(
            water_depth=self.h.copy(),
            velocity_u=self.u.copy(),
            velocity_v=self.v.copy(),
            time=self.time,
        )

    def get_maximum_depth(self) -> float:
        """Get maximum water depth."""
        return float(np.max(self.h))

    def get_total_volume(self) -> float:
        """Get total water volume in cubic meters."""
        cell_area = self.dx * self.dy
        return float(np.sum(self.h) * cell_area)

    def get_flood_extent(self, threshold: float = 0.01) -> float:
        """Get flood extent area in square meters.

        Args:
            threshold: Minimum depth to count as flooded

        Returns:
            Flooded area in m²
        """
        cell_area = self.dx * self.dy
        flooded_cells = np.sum(self.h > threshold)
        return float(flooded_cells * cell_area)

    def get_velocity_magnitude(self) -> np.ndarray:
        """Get velocity magnitude field."""
        return np.sqrt(self.u**2 + self.v**2)

    def get_froude_number(self) -> np.ndarray:
        """Get Froude number field (Fr = u/√(gh))."""
        h_safe = np.maximum(self.h, 0.001)
        velocity = self.get_velocity_magnitude()
        celerity = np.sqrt(self.g * h_safe)
        return velocity / celerity

    def export_results(self) -> Dict[str, Any]:
        """Export simulation results.

        Returns:
            Dictionary with simulation data
        """
        return {
            "grid_size": (self.nx, self.ny),
            "grid_spacing": (self.dx, self.dy),
            "time": self.time,
            "timestep": self.timestep,
            "water_depth": self.h.tolist(),
            "velocity_u": self.u.tolist(),
            "velocity_v": self.v.tolist(),
            "max_depth": self.get_maximum_depth(),
            "total_volume": self.get_total_volume(),
            "flood_extent": self.get_flood_extent(),
            "max_velocity": float(np.max(self.get_velocity_magnitude())),
        }
