"""GIS module for flood prediction world model.

This package provides GIS capabilities for importing and processing
spatial data in various formats (GeoTIFF, Shapefile, GeoJSON).
"""

from .models import (
    BoundingBox,
    SpatialReferenceSystem,
    DigitalTerrainModel,
    WaterSurfaceGeometry,
    WeatherParameters,
    SimulationConfig,
    SimulationResult,
    VectorFormat,
    RasterFormat,
    SpatialDataType,
)

from .importer import GISImporter, VectorData, GISImportError

from .mesh_generator import (
    Mesh3D,
    TerrainMeshGenerator,
    WaterSurfaceMeshGenerator,
    LODMeshGenerator,
    generate_terrain_mesh,
    generate_water_mesh,
)

__all__ = [
    # Models
    "BoundingBox",
    "SpatialReferenceSystem",
    "DigitalTerrainModel",
    "WaterSurfaceGeometry",
    "WeatherParameters",
    "SimulationConfig",
    "SimulationResult",
    "VectorFormat",
    "RasterFormat",
    "SpatialDataType",
    # Importer
    "GISImporter",
    "VectorData",
    "GISImportError",
    # Mesh Generator
    "Mesh3D",
    "TerrainMeshGenerator",
    "WaterSurfaceMeshGenerator",
    "LODMeshGenerator",
    "generate_terrain_mesh",
    "generate_water_mesh",
]
