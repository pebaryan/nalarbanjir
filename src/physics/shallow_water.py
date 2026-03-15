"""Shallow Water Wave Equation Solver.

This module implements the 2D shallow water wave equations that govern
flood dynamics, serving as the physical core of the world model.

The shallow water equations describe:
- Water surface elevation (η)
- Depth-averaged velocity components (u, v)
- Mass and momentum conservation
"""

import logging
import numpy as np
import torch
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class WaterState:
    """Represents the state of water at a given time."""

    # Water surface elevation (m)
    elevation: np.ndarray

    # Depth-averaged velocity components (m/s)
    velocity_x: np.ndarray
    velocity_y: np.ndarray

    # Water depth (m)
    depth: np.ndarray

    # Time step
    time: float


class ShallowWaterSolver:
    """Solver for 2D shallow water wave equations.

    The shallow water equations are:

    ∂h/∂t + ∂(hu)/∂x + ∑(hv)/∂y = 0  (Continuity)
    ∂(hu)/∂t + ∂(hu²)/∂x + ∂(huv)/∂y = -gh∂η/∂x + friction  (Momentum x)
    ∂(hv)/∂t + ∂(huv)/∂x + ∂(hv²)/∂y = -gh∂η/∂y + friction  (Momentum y)
    """

    def __init__(self, config: Dict, grid_resolution: Tuple[int, int] = (100, 100)):
        """Initialize the shallow water solver.

        Args:
            config: Configuration dictionary with physics parameters
            grid_resolution: Number of grid points in x and y directions
        """
        self.config = config
        self.grid_resolution = grid_resolution
        self.nx, self.ny = grid_resolution

        # Physical parameters
        self.g = config.get("gravity", 9.81)  # Gravitational acceleration (m/s²)
        self.f = config.get("coriolis", 0.0)  # Coriolis parameter
        self.rh = config.get("bottom_friction", 0.02)  # Bottom friction coefficient

        # Initialize grid
        self._initialize_grid()

        # Initialize state variables
        self.state = self._init_state()

        # Time integration
        self.dt = config.get("time_step", 1.0)  # Time step (s)
        self.time = 0.0

        logger.info(f"ShallowWaterSolver initialized: {self.nx}x{self.ny} grid")
        logger.info(f"  Domain: {self.Lx:.1f}m × {self.Ly:.1f}m")
        logger.info(f"  Grid spacing: dx={self.dx:.1f}m, dy={self.dy:.1f}m")
        logger.info(
            f"  Gravity: {self.g} m/s², Coriolis: {self.f}, Friction: {self.rh}"
        )
        logger.info(f"  Time step: {self.dt}s")

    def _initialize_grid(self):
        """Initialize the computational grid."""
        # Domain dimensions (can be configured)
        self.Lx = self.config.get("domain_x", 10000.0)  # Domain length in x (m)
        self.Ly = self.config.get("domain_y", 10000.0)  # Domain length in y (m)

        # Grid spacing
        self.dx = self.Lx / (self.nx - 1)
        self.dy = self.Ly / (self.ny - 1)

        # Create grid coordinates
        self.x = np.linspace(0, self.Lx, self.nx)
        self.y = np.linspace(0, self.Ly, self.ny)
        self.X, self.Y = np.meshgrid(self.x, self.y, indexing="ij")

        # Compute areas and distances for finite volume method
        self.area = self.dx * self.dy

        print(f"Grid initialized: {self.nx}x{self.ny} cells")
        print(f"Domain: {self.Lx:.0f}m × {self.Ly:.0f}m")
        print(f"Grid spacing: dx={self.dx:.1f}m, dy={self.dy:.1f}m")

    def _init_state(self) -> WaterState:
        """Initialize water state variables."""
        # Initialize water depth with possible initial conditions
        depth = self._init_water_depth()

        # Initialize velocity field
        velocity_x = np.zeros_like(depth)
        velocity_y = np.zeros_like(depth)

        # Initialize elevation from depth (assuming reference level at z=0)
        elevation = depth.copy()

        return WaterState(
            elevation=elevation,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            depth=depth,
            time=0.0,
        )

    def _init_water_depth(self) -> np.ndarray:
        """Initialize water depth distribution.

        Creates a realistic initial depth profile that may include:
        - Baseline terrain depth
        - Initial water volume
        - Potential flood zones
        """
        depth = np.zeros((self.ny, self.nx))

        # Add terrain variations (simplified as sinusoidal)
        terrain_amplitude = self.config.get("terrain_amplitude", 2.0)
        terrain_wavelength = self.config.get("terrain_wavelength", 2000.0)

        for i in range(self.ny):
            for j in range(self.nx):
                # Terrain elevation
                terrain_z = terrain_amplitude * np.sin(
                    2 * np.pi * self.X[i, j] / terrain_wavelength
                )

                # Initial water depth (deeper in potential flood zones)
                base_depth = 1.0 + 0.5 * np.sin(
                    2 * np.pi * self.Y[i, j] / terrain_wavelength
                )

                # Combine terrain and water
                depth[i, j] = max(0.5, base_depth - terrain_z)

        return depth

    def evolve(self, steps: int = 100) -> List[WaterState]:
        """Evolve the water state over multiple time steps.

        Args:
            steps: Number of time steps to simulate

        Returns:
            List of water states at each time step
        """
        logger.info(f"Starting evolution: {steps} steps")
        states = [self.state]

        # Log initial state
        initial_depth = np.mean(self.state.depth)
        logger.debug(f"Initial mean depth: {initial_depth:.4f}m")

        for step in range(steps):
            # Advance time
            self.time += self.dt

            # Compute fluxes and update state
            self._compute_fluxes()
            self._update_state()

            # Apply boundary conditions
            self._apply_boundary_conditions()

            # Store state
            new_state = WaterState(
                elevation=self.state.elevation.copy(),
                velocity_x=self.state.velocity_x.copy(),
                velocity_y=self.state.velocity_y.copy(),
                depth=self.state.depth.copy(),
                time=self.time,
            )
            states.append(new_state)

            # Log progress every 10% or for significant changes
            if steps > 0 and (step + 1) % max(1, steps // 10) == 0:
                current_depth = np.mean(new_state.depth)
                logger.debug(
                    f"Step {step + 1}/{steps}: mean depth = {current_depth:.4f}m, time = {self.time:.2f}s"
                )

        logger.info(f"Evolution completed: {len(states)} states generated")
        logger.info(
            f"Final time: {self.time:.2f}s, final mean depth: {np.mean(states[-1].depth):.4f}m"
        )
        return states

    def _compute_fluxes(self):
        """Compute fluxes for mass and momentum conservation."""
        h = self.state.depth
        u = self.state.velocity_x
        v = self.state.velocity_y
        g = self.g

        # Compute hydrostatic pressure gradients
        grad_hx, grad_hy = self._compute_depth_gradients(h)

        # Momentum fluxes (advection terms)
        flux_mom_x = u**2 + g * h * grad_hx
        flux_mom_y = v**2 + g * h * grad_hy

        # Friction terms (bottom drag)
        friction_x = self.rh * u * np.sqrt(u**2 + v**2)
        friction_y = self.rh * v * np.sqrt(u**2 + v**2)

        # Update velocity using momentum equations
        du_dt = -flux_mom_x + friction_x
        dv_dt = -flux_mom_y + friction_y

        # Update velocity
        self.state.velocity_x += self.dt * du_dt
        self.state.velocity_y += self.dt * dv_dt

    def _compute_depth_gradients(
        self, depth: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute depth gradients in x and y directions.

        Args:
            depth: Water depth array

        Returns:
            Tuple of (gradient_x, gradient_y) arrays
        """
        # Finite difference gradients
        grad_hx = np.gradient(depth, self.dx, axis=1)
        grad_hy = np.gradient(depth, self.dy, axis=0)

        return grad_hx, grad_hy

    def _update_state(self):
        """Update water state based on computed fluxes."""
        h = self.state.depth
        u = self.state.velocity_x
        v = self.state.velocity_y

        # Continuity equation: update water depth
        grad_hx, grad_hy = self._compute_depth_gradients(h)

        # Depth change due to advection
        dh_dt_adv = -(u * grad_hx + v * grad_hy)

        # Update depth
        self.state.depth += self.dt * dh_dt_adv

        # Ensure non-negative depth
        self.state.depth = np.maximum(self.state.depth, 0.01)

        # Update elevation
        self.state.elevation = self.state.depth

    def _apply_boundary_conditions(self):
        """Apply boundary conditions at domain edges."""
        h = self.state.depth
        u = self.state.velocity_x
        v = self.state.velocity_y

        # No-flow boundaries (reflecting walls)
        # Left and right boundaries
        u[:, 0] = -u[:, 1]
        u[:, -1] = -u[:, -2]

        # Top and bottom boundaries
        v[0, :] = -v[1, :]
        v[-1, :] = -v[-2, :]

        # Free-slip condition for velocity
        self.state.velocity_x = u
        self.state.velocity_y = v

    def get_water_surface(self) -> np.ndarray:
        """Get the current water surface elevation.

        Returns:
            Water surface elevation array
        """
        return self.state.elevation.copy()

    def get_velocity_field(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get the current velocity field.

        Returns:
            Tuple of (velocity_x, velocity_y) arrays
        """
        return (self.state.velocity_x.copy(), self.state.velocity_y.copy())

    def compute_flood_risk(self, threshold_depth: float = 2.0) -> np.ndarray:
        """Compute flood risk based on water depth.

        Args:
            threshold_depth: Depth threshold for flood conditions

        Returns:
            Flood risk indicator array
        """
        depth = self.state.depth

        # Risk levels: 0 (no risk), 1 (moderate), 2 (high), 3 (severe)
        risk = np.zeros_like(depth)

        risk[depth >= threshold_depth] = 1
        risk[depth >= threshold_depth * 1.5] = 2
        risk[depth >= threshold_depth * 2.0] = 3

        return risk

    def export_state(self) -> Dict:
        """Export current state as dictionary.

        Returns:
            State dictionary containing all simulation data
        """
        return {
            "time": self.time,
            "grid": {
                "nx": self.nx,
                "ny": self.ny,
                "dx": self.dx,
                "dy": self.dy,
                "domain_x": self.Lx,
                "domain_y": self.Ly,
            },
            "physics": {
                "gravity": self.g,
                "coriolis": self.f,
                "bottom_friction": self.rh,
            },
            "state": {
                "elevation": self.state.elevation,
                "velocity_x": self.state.velocity_x,
                "velocity_y": self.state.velocity_y,
                "depth": self.state.depth,
            },
        }


class WavePropagationAnalyzer:
    """Analyzes wave propagation characteristics in the water surface.

    This analyzer extracts important wave properties:
    - Wave speed and direction
    - Energy distribution
    - Wavefront evolution
    """

    def __init__(self, solver: ShallowWaterSolver):
        """Initialize the wave propagation analyzer.

        Args:
            solver: Shallow water solver instance
        """
        self.solver = solver

    def analyze_wave_propagation(self, state: WaterState) -> Dict:
        """Analyze wave propagation characteristics.

        Args:
            state: Current water state

        Returns:
            Dictionary containing wave analysis results
        """
        h = state.depth
        u = state.velocity_x
        v = state.velocity_y

        # Wave celerity (speed of shallow water waves)
        celerity = np.sqrt(self.solver.g * h)

        # Wave propagation direction
        propagation_angle = np.arctan2(v, u)

        # Wave energy density
        kinetic_energy = 0.5 * h * (u**2 + v**2)
        potential_energy = 0.5 * self.solver.g * h**2
        total_energy = kinetic_energy + potential_energy

        return {
            "celerity": celerity,
            "propagation_angle": propagation_angle,
            "kinetic_energy": kinetic_energy,
            "potential_energy": potential_energy,
            "total_energy": total_energy,
            "mean_celerity": np.mean(celerity),
            "max_celerity": np.max(celerity),
            "min_celerity": np.min(celerity),
        }

    def detect_wave_sources(
        self, state: WaterState, energy_threshold: float = None
    ) -> List[Tuple[int, int]]:
        """Detect potential wave source locations.

        Args:
            state: Current water state
            energy_threshold: Energy threshold for source detection

        Returns:
            List of (row, col) coordinates of wave sources
        """
        analysis = self.analyze_wave_propagation(state)

        if energy_threshold is None:
            energy_threshold = analysis["mean_celerity"] ** 2

        # Identify high-energy regions as potential wave sources
        energy = analysis["total_energy"]

        # Find local maxima in energy field
        sources = []

        for i in range(1, self.solver.ny - 1):
            for j in range(1, self.solver.nx - 1):
                if energy[i, j] > energy_threshold and self._is_local_maximal(
                    energy, i, j
                ):
                    sources.append((i, j))

        return sources

    def _is_local_maximal(self, array: np.ndarray, i: int, j: int) -> bool:
        """Check if a point is a local maximum.

        Args:
            array: Input array
            i: Row index
            j: Column index

        Returns:
            True if the point is a local maximum
        """
        value = array[i, j]

        # Compare with neighbors
        neighbors = [array[i - 1, j], array[i + 1, j], array[i, j - 1], array[i, j + 1]]

        return all(value >= neighbor for neighbor in neighbors)
