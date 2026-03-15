"""Boundary condition handling for flood dynamics simulation.

This module provides various boundary condition implementations
for the shallow water wave equation solver.
"""

import numpy as np
from typing import Tuple, Dict, Any
from enum import Enum


class BoundaryConditionType(Enum):
    """Types of boundary conditions."""

    NO_FLOW = "no_flow"  # Reflective/wall boundary
    FREE_SLIP = "free_slip"  # Free-slip boundary
    OPEN = "open"  # Open/radiation boundary
    PRESCRIBED_FLOW = "prescribed_flow"  # Prescribed velocity boundary
    PRESCRIBED_HEIGHT = "prescribed_height"  # Prescribed water height boundary


class BoundaryConditions:
    """Handles boundary conditions for the shallow water solver."""

    def __init__(self, config: Dict[str, Any], grid_shape: Tuple[int, int]):
        """Initialize boundary conditions handler.

        Args:
            config: Configuration dictionary
            grid_shape: Shape of the computational grid (ny, nx)
        """
        self.config = config
        self.grid_shape = grid_shape
        self.ny, self.nx = grid_shape

        # Default boundary condition type
        self.default_type = BoundaryConditionType[
            config.get("boundary_type", "NO_FLOW").upper()
        ]

        # Boundary condition specifications for each side
        self.boundary_specs = {
            "left": self._parse_boundary_config(config.get("left_boundary", {})),
            "right": self._parse_boundary_config(config.get("right_boundary", {})),
            "top": self._parse_boundary_config(config.get("top_boundary", {})),
            "bottom": self._parse_boundary_config(config.get("bottom_boundary", {})),
        }

    def _parse_boundary_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse boundary configuration.

        Args:
            config: Boundary configuration dictionary

        Returns:
            Parsed boundary configuration
        """
        if not config:
            return {"type": self.default_type}

        bc_type_str = config.get("type", self.default_type.value).upper()
        try:
            bc_type = BoundaryConditionType[bc_type_str]
        except KeyError:
            bc_type = self.default_type

        return {
            "type": bc_type,
            "value": config.get("value", 0.0),
            "time_dependent": config.get("time_dependent", False),
        }

    def apply_boundary_conditions(
        self, h: np.ndarray, u: np.ndarray, v: np.ndarray, time: float = 0.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply boundary conditions to depth and velocity fields.

        Args:
            h: Water depth array (ny, nx)
            u: x-velocity array (ny, nx)
            v: y-velocity array (ny, nx)
            time: Current simulation time

        Returns:
            Tuple of (h, u, v) with boundary conditions applied
        """
        # Make copies to avoid modifying originals
        h_bc = h.copy()
        u_bc = u.copy()
        v_bc = v.copy()

        # Apply boundary conditions to each side
        h_bc, u_bc, v_bc = self._apply_left_boundary(h_bc, u_bc, v_bc, time)
        h_bc, u_bc, v_bc = self._apply_right_boundary(h_bc, u_bc, v_bc, time)
        h_bc, u_bc, v_bc = self._apply_top_boundary(h_bc, u_bc, v_bc, time)
        h_bc, u_bc, v_bc = self._apply_bottom_boundary(h_bc, u_bc, v_bc, time)

        return h_bc, u_bc, v_bc

    def _apply_left_boundary(
        self, h: np.ndarray, u: np.ndarray, v: np.ndarray, time: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply boundary conditions at left boundary (x=0)."""
        bc = self.boundary_specs["left"]

        if bc["type"] == BoundaryConditionType.NO_FLOW:
            # Reflective boundary: normal velocity = 0
            u[:, 0] = 0.0
            # Tangential velocity can be free-slip or no-slip
            v[:, 0] = v[:, 1]  # Free-slip condition

        elif bc["type"] == BoundaryConditionType.FREE_SLIP:
            # Free-slip: normal velocity = 0, tangential derivative = 0
            u[:, 0] = 0.0
            v[:, 0] = v[:, 1]

        elif bc["type"] == BoundaryConditionType.OPEN:
            # Open boundary: extrapolate from interior
            # Simple approach: copy values from first interior point
            if self.nx > 1:
                h[:, 0] = h[:, 1]
                u[:, 0] = u[:, 1]
                v[:, 0] = v[:, 1]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_FLOW:
            # Prescribed velocity
            if self.nx > 1:
                u[:, 0] = (
                    bc["value"]
                    if not bc["time_dependent"]
                    else bc["value"] * np.sin(time)
                )
                h[:, 0] = h[:, 1]  # Extrapolate height
                v[:, 0] = v[:, 1]  # Free-slip for tangential

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_HEIGHT:
            # Prescribed water height
            h[:, 0] = (
                bc["value"] if not bc["time_dependent"] else bc["value"] * np.sin(time)
            )
            # Zero normal velocity for prescribed height
            u[:, 0] = 0.0
            v[:, 0] = v[:, 1]  # Free-slip tangential

        return h, u, v

    def _apply_right_boundary(
        self, h: np.ndarray, u: np.ndarray, v: np.ndarray, time: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply boundary conditions at right boundary (x=Lx)."""
        bc = self.boundary_specs["right"]

        if bc["type"] == BoundaryConditionType.NO_FLOW:
            # Reflective boundary: normal velocity = 0
            u[:, -1] = 0.0
            v[:, -1] = v[:, -2]  # Free-slip

        elif bc["type"] == BoundaryConditionType.FREE_SLIP:
            # Free-slip: normal velocity = 0, tangential derivative = 0
            u[:, -1] = 0.0
            v[:, -1] = v[:, -2]

        elif bc["type"] == BoundaryConditionType.OPEN:
            # Open boundary: extrapolate from interior
            if self.nx > 1:
                h[:, -1] = h[:, -2]
                u[:, -1] = u[:, -2]
                v[:, -1] = v[:, -2]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_FLOW:
            # Prescribed velocity (negative for outflow convention)
            if self.nx > 1:
                u[:, -1] = (
                    -bc["value"]
                    if not bc["time_dependent"]
                    else -bc["value"] * np.sin(time)
                )
                h[:, -1] = h[:, -2]
                v[:, -1] = v[:, -2]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_HEIGHT:
            # Prescribed water height
            h[:, -1] = (
                bc["value"] if not bc["time_dependent"] else bc["value"] * np.sin(time)
            )
            u[:, -1] = 0.0  # Zero normal velocity
            v[:, -1] = v[:, -2]  # Free-slip tangential

        return h, u, v

    def _apply_top_boundary(
        self, h: np.ndarray, u: np.ndarray, v: np.ndarray, time: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply boundary conditions at top boundary (y=Ly)."""
        bc = self.boundary_specs["top"]

        if bc["type"] == BoundaryConditionType.NO_FLOW:
            # Reflective boundary: normal velocity = 0
            v[-1, :] = 0.0
            u[-1, :] = u[-2, :]  # Free-slip

        elif bc["type"] == BoundaryConditionType.FREE_SLIP:
            # Free-slip: normal velocity = 0, tangential derivative = 0
            v[-1, :] = 0.0
            u[-1, :] = u[-2, :]

        elif bc["type"] == BoundaryConditionType.OPEN:
            # Open boundary: extrapolate from interior
            if self.ny > 1:
                h[-1, :] = h[-2, :]
                u[-1, :] = u[-2, :]
                v[-1, :] = v[-2, :]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_FLOW:
            # Prescribed velocity
            if self.ny > 1:
                v[-1, :] = (
                    bc["value"]
                    if not bc["time_dependent"]
                    else bc["value"] * np.sin(time)
                )
                h[-1, :] = h[-2, :]
                u[-1, :] = u[-2, :]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_HEIGHT:
            # Prescribed water height
            h[-1, :] = (
                bc["value"] if not bc["time_dependent"] else bc["value"] * np.sin(time)
            )
            v[-1, :] = 0.0  # Zero normal velocity
            u[-1, :] = u[-2, :]  # Free-slip tangential

        return h, u, v

    def _apply_bottom_boundary(
        self, h: np.ndarray, u: np.ndarray, v: np.ndarray, time: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply boundary conditions at bottom boundary (y=0)."""
        bc = self.boundary_specs["bottom"]

        if bc["type"] == BoundaryConditionType.NO_FLOW:
            # Reflective boundary: normal velocity = 0
            v[0, :] = 0.0
            u[0, :] = u[1, :]  # Free-slip

        elif bc["type"] == BoundaryConditionType.FREE_SLIP:
            # Free-slip: normal velocity = 0, tangential derivative = 0
            v[0, :] = 0.0
            u[0, :] = u[1, :]

        elif bc["type"] == BoundaryConditionType.OPEN:
            # Open boundary: extrapolate from interior
            if self.ny > 1:
                h[0, :] = h[1, :]
                u[0, :] = u[1, :]
                v[0, :] = v[1, :]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_FLOW:
            # Prescribed velocity (negative for inflow convention)
            if self.ny > 1:
                v[0, :] = (
                    -bc["value"]
                    if not bc["time_dependent"]
                    else -bc["value"] * np.sin(time)
                )
                h[0, :] = h[1, :]
                u[0, :] = u[1, :]

        elif bc["type"] == BoundaryConditionType.PRESCRIBED_HEIGHT:
            # Prescribed water height
            h[0, :] = (
                bc["value"] if not bc["time_dependent"] else bc["value"] * np.sin(time)
            )
            v[0, :] = 0.0  # Zero normal velocity
            u[0, :] = u[1, :]  # Free-slip tangential

        return h, u, v

    def get_boundary_info(self) -> Dict[str, Any]:
        """Get information about current boundary conditions.

        Returns:
            Dictionary containing boundary condition information
        """
        info = {
            "grid_shape": self.grid_shape,
            "default_type": self.default_type.value,
            "boundaries": {},
        }

        for side, spec in self.boundary_specs.items():
            info["boundaries"][side] = {
                "type": spec["type"].value,
                "value": spec["value"],
                "time_dependent": spec["time_dependent"],
            }

        return info


# Utility functions for common boundary condition setups
def create_channel_flow_bc(
    inlet_velocity: float = 1.0,
    outlet_velocity: float = 1.0,
    wall_type: str = "no_slip",
) -> Dict[str, Dict[str, Any]]:
    """Create boundary conditions for channel flow.

    Args:
        inlet_velocity: Velocity at inlet (left boundary)
        outlet_velocity: Velocity at outlet (right boundary)
        wall_type: Type of wall boundary ("no_slip" or "free_slip")

    Returns:
        Boundary configuration dictionary
    """
    bc_type = (
        BoundaryConditionType.NO_FLOW
        if wall_type == "no_slip"
        else BoundaryConditionType.FREE_SLIP
    )

    return {
        "left": {
            "type": BoundaryConditionType.PRESCRIBED_FLOW.value,
            "value": inlet_velocity,
        },
        "right": {
            "type": BoundaryConditionType.PRESCRIBED_FLOW.value,
            "value": -outlet_velocity,  # Negative for outflow
        },
        "top": {"type": bc_type.value},
        "bottom": {"type": bc_type.value},
    }


def create_dam_break_bc(
    left_water_height: float = 2.0, right_water_height: float = 0.5
) -> Dict[str, Dict[str, Any]]:
    """Create boundary conditions for dam break problem.

    Args:
        left_water_height: Water height in left reservoir
        right_water_height: Water height in right reservoir

    Returns:
        Boundary configuration dictionary
    """
    return {
        "left": {
            "type": BoundaryConditionType.PRESCRIBED_HEIGHT.value,
            "value": left_water_height,
        },
        "right": {
            "type": BoundaryConditionType.PRESCRIBED_HEIGHT.value,
            "value": right_water_height,
        },
        "top": {"type": BoundaryConditionType.NO_FLOW.value},
        "bottom": {"type": BoundaryConditionType.NO_FLOW.value},
    }
