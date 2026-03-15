"""Physics module for flood prediction world model.

Contains the shallow water wave equation solver, terrain modeling,
and boundary condition handling for flood dynamics simulation.
"""

from .shallow_water import ShallowWaterSolver
from .terrain import TerrainModel

__all__ = ["ShallowWaterSolver", "TerrainModel", "BoundaryConditions"]
