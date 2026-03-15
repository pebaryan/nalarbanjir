"""Core data models for GIS-based flood simulation.

This module defines the data structures used throughout the application
for spatial data representation, terrain models, and simulation parameters.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from enum import Enum
import numpy as np
from datetime import datetime


class SpatialDataType(Enum):
    """Types of spatial data supported."""

    RASTER = "raster"
    VECTOR = "vector"
    MESH = "mesh"
    POINT_CLOUD = "point_cloud"


class VectorFormat(Enum):
    """Supported vector file formats."""

    SHAPEFILE = "shp"
    GEOJSON = "geojson"
    GEOPACKAGE = "gpkg"
    KML = "kml"


class RasterFormat(Enum):
    """Supported raster file formats."""

    GEOTIFF = "tif"
    ASCII_GRID = "asc"
    HDF5 = "h5"
    NETCDF = "nc"


@dataclass
class BoundingBox:
    """Spatial bounding box with CRS information.

    Attributes:
        min_x: Minimum X coordinate
        min_y: Minimum Y coordinate
        max_x: Maximum X coordinate
        max_y: Maximum Y coordinate
        epsg: EPSG code for coordinate reference system
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    epsg: int = 4326  # Default to WGS84

    @property
    def width(self) -> float:
        """Get width of bounding box."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Get height of bounding box."""
        return self.max_y - self.min_y

    @property
    def center(self) -> Tuple[float, float]:
        """Get center point of bounding box."""
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    @property
    def area(self) -> float:
        """Get area of bounding box."""
        return self.width * self.height

    def contains(self, x: float, y: float) -> bool:
        """Check if point is within bounding box."""
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "epsg": self.epsg,
            "width": self.width,
            "height": self.height,
            "center": self.center,
            "area": self.area,
        }


@dataclass
class SpatialReferenceSystem:
    """Coordinate reference system definition.

    Attributes:
        epsg_code: EPSG code (e.g., 4326 for WGS84, 3857 for Web Mercator)
        name: Human-readable name
        units: Units of measurement (meters, degrees, etc.)
        proj4_string: PROJ4 projection string
    """

    epsg_code: int
    name: str = ""
    units: str = ""
    proj4_string: str = ""

    def __post_init__(self):
        """Initialize derived attributes."""
        if not self.name:
            self.name = self._get_name_from_epsg()
        if not self.units:
            self.units = self._get_units_from_epsg()

    def _get_name_from_epsg(self) -> str:
        """Get CRS name from EPSG code."""
        epsg_names = {
            4326: "WGS 84",
            3857: "Web Mercator",
            32633: "UTM Zone 33N",
            25833: "ETRS89 / UTM zone 33N",
        }
        return epsg_names.get(self.epsg_code, f"EPSG:{self.epsg_code}")

    def _get_units_from_epsg(self) -> str:
        """Get units from EPSG code."""
        geographic_epsg = [4326, 4267, 4269]  # WGS84, NAD27, NAD83
        if self.epsg_code in geographic_epsg:
            return "degrees"
        return "meters"

    def is_geographic(self) -> bool:
        """Check if CRS is geographic (uses degrees)."""
        return self.units == "degrees"

    def is_projected(self) -> bool:
        """Check if CRS is projected (uses meters)."""
        return self.units == "meters"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "epsg_code": self.epsg_code,
            "name": self.name,
            "units": self.units,
            "proj4_string": self.proj4_string,
        }


@dataclass
class DigitalTerrainModel:
    """Digital Terrain Model (DTM) data structure.

    Attributes:
        elevation_data: 2D numpy array of elevation values
        bounds: Spatial bounding box
        resolution: Grid resolution (x, y) in CRS units
        crs: Coordinate reference system
        nodata_value: Value representing no data
        metadata: Additional metadata
    """

    elevation_data: np.ndarray
    bounds: BoundingBox
    resolution: Tuple[float, float]
    crs: SpatialReferenceSystem
    nodata_value: float = -9999.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate data."""
        if not isinstance(self.elevation_data, np.ndarray):
            raise TypeError("elevation_data must be a numpy array")
        if self.elevation_data.ndim != 2:
            raise ValueError("elevation_data must be 2D")

    @property
    def shape(self) -> Tuple[int, int]:
        """Get shape of elevation data (rows, cols)."""
        return self.elevation_data.shape

    @property
    def height(self) -> int:
        """Get number of rows."""
        return self.elevation_data.shape[0]

    @property
    def width(self) -> int:
        """Get number of columns."""
        return self.elevation_data.shape[1]

    @property
    def min_elevation(self) -> float:
        """Get minimum elevation (excluding nodata)."""
        valid_data = self.elevation_data[self.elevation_data != self.nodata_value]
        return float(valid_data.min()) if len(valid_data) > 0 else 0.0

    @property
    def max_elevation(self) -> float:
        """Get maximum elevation (excluding nodata)."""
        valid_data = self.elevation_data[self.elevation_data != self.nodata_value]
        return float(valid_data.max()) if len(valid_data) > 0 else 0.0

    @property
    def mean_elevation(self) -> float:
        """Get mean elevation (excluding nodata)."""
        valid_data = self.elevation_data[self.elevation_data != self.nodata_value]
        return float(valid_data.mean()) if len(valid_data) > 0 else 0.0

    def get_elevation_at(self, x: float, y: float) -> Optional[float]:
        """Get elevation at specific coordinates using bilinear interpolation.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Elevation value or None if out of bounds
        """
        if not self.bounds.contains(x, y):
            return None

        # Convert geo coordinates to array indices
        col = (x - self.bounds.min_x) / self.resolution[0]
        row = (self.bounds.max_y - y) / self.resolution[1]

        # Bilinear interpolation
        row0, col0 = int(row), int(col)
        row1, col1 = min(row0 + 1, self.height - 1), min(col0 + 1, self.width - 1)

        if row0 >= self.height or col0 >= self.width:
            return None

        # Get corner values
        q11 = self.elevation_data[row1, col0]
        q12 = self.elevation_data[row1, col1]
        q21 = self.elevation_data[row0, col0]
        q22 = self.elevation_data[row0, col1]

        # Check for nodata
        if any(v == self.nodata_value for v in [q11, q12, q21, q22]):
            return None

        # Interpolation weights
        dy = row - row0
        dx = col - col0

        # Bilinear interpolation
        elevation = (
            q11 * (1 - dx) * (1 - dy)
            + q21 * dx * (1 - dy)
            + q12 * (1 - dx) * dy
            + q22 * dx * dy
        )

        return float(elevation)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "shape": self.shape,
            "bounds": self.bounds.to_dict(),
            "resolution": self.resolution,
            "crs": self.crs.to_dict(),
            "min_elevation": self.min_elevation,
            "max_elevation": self.max_elevation,
            "mean_elevation": self.mean_elevation,
            "nodata_value": self.nodata_value,
            "metadata": self.metadata,
        }


@dataclass
class WaterSurfaceGeometry:
    """Water surface geometry for 3D visualization.

    Attributes:
        vertices: Nx3 array of vertex coordinates (x, y, z)
        faces: Mx3 array of face indices (triangles)
        uvs: Texture coordinates
        normals: Vertex normals
        timestamp: Time of measurement
    """

    vertices: np.ndarray
    faces: np.ndarray
    uvs: Optional[np.ndarray] = None
    normals: Optional[np.ndarray] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate geometry data."""
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("vertices must be Nx3 array")
        if self.faces.ndim != 2 or self.faces.shape[1] != 3:
            raise ValueError("faces must be Mx3 array")

    @property
    def vertex_count(self) -> int:
        """Get number of vertices."""
        return self.vertices.shape[0]

    @property
    def face_count(self) -> int:
        """Get number of faces."""
        return self.faces.shape[0]

    def calculate_normals(self) -> np.ndarray:
        """Calculate face normals."""
        # Get vertices for each face
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]

        # Calculate face normals
        edges1 = v1 - v0
        edges2 = v2 - v0
        normals = np.cross(edges1, edges2)

        # Normalize
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normals = normals / norms

        return normals

    def to_threejs_format(self) -> Dict[str, Any]:
        """Export to Three.js compatible format."""
        return {
            "vertices": self.vertices.flatten().tolist(),
            "indices": self.faces.flatten().tolist(),
            "uvs": self.uvs.flatten().tolist() if self.uvs is not None else [],
            "normals": self.normals.flatten().tolist()
            if self.normals is not None
            else [],
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
        }


@dataclass
class WeatherParameters:
    """Weather simulation parameters.

    Attributes:
        rainfall_intensity: Rainfall intensity (mm/hour)
        rainfall_duration: Duration of rainfall (hours)
        wind_speed: Wind speed (m/s)
        wind_direction: Wind direction (degrees from north)
        temperature: Air temperature (Celsius)
        humidity: Relative humidity (0-1)
        timestamp: Time of weather data
    """

    rainfall_intensity: float = 0.0  # mm/hour
    rainfall_duration: float = 0.0  # hours
    wind_speed: float = 0.0  # m/s
    wind_direction: float = 0.0  # degrees from north
    temperature: float = 20.0  # Celsius
    humidity: float = 0.5  # 0-1
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_rainfall(self) -> float:
        """Calculate total rainfall amount."""
        return self.rainfall_intensity * self.rainfall_duration

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rainfall_intensity": self.rainfall_intensity,
            "rainfall_duration": self.rainfall_duration,
            "total_rainfall": self.total_rainfall,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SimulationConfig:
    """Configuration for flood simulation.

    Attributes:
        time_step: Simulation time step (seconds)
        total_time: Total simulation time (seconds)
        output_interval: Interval between outputs (seconds)
        physics_params: Physics simulation parameters
        numerical_params: Numerical solver parameters
    """

    time_step: float = 1.0  # seconds
    total_time: float = 3600.0  # seconds (1 hour)
    output_interval: float = 60.0  # seconds

    # Physics parameters
    gravity: float = 9.81  # m/s²
    manning_coefficient: float = 0.03  # Manning's n
    diffusion_coefficient: float = 0.1  # Numerical diffusion

    # Numerical parameters
    max_iterations: int = 10000
    convergence_threshold: float = 1e-6
    use_gpu: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "time_step": self.time_step,
            "total_time": self.total_time,
            "output_interval": self.output_interval,
            "num_outputs": int(self.total_time / self.output_interval),
            "gravity": self.gravity,
            "manning_coefficient": self.manning_coefficient,
            "diffusion_coefficient": self.diffusion_coefficient,
            "max_iterations": self.max_iterations,
            "use_gpu": self.use_gpu,
        }


@dataclass
class SimulationResult:
    """Result of flood simulation.

    Attributes:
        water_depth: Time series of water depth arrays
        water_surface: Time series of water surface geometries
        timestamps: Simulation timestamps
        max_water_depth: Maximum water depth reached
        flooded_area: Total flooded area
        statistics: Simulation statistics
    """

    water_depth: List[np.ndarray] = field(default_factory=list)
    water_surface: List[WaterSurfaceGeometry] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    max_water_depth: float = 0.0
    flooded_area: float = 0.0
    statistics: Dict[str, Any] = field(default_factory=dict)

    def add_timestep(
        self, depth: np.ndarray, surface: WaterSurfaceGeometry, timestamp: float
    ):
        """Add a simulation timestep."""
        self.water_depth.append(depth)
        self.water_surface.append(surface)
        self.timestamps.append(timestamp)

        # Update statistics
        current_max = np.max(depth)
        if current_max > self.max_water_depth:
            self.max_water_depth = float(current_max)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "num_timesteps": len(self.timestamps),
            "timestamps": self.timestamps,
            "max_water_depth": self.max_water_depth,
            "flooded_area": self.flooded_area,
            "statistics": self.statistics,
        }
