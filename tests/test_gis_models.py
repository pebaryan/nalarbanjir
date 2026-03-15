"""Tests for GIS data models.

This module contains comprehensive tests for the core data models
used in the GIS-based flood simulation system.
"""

import pytest
import numpy as np
from datetime import datetime

# Import the models
import sys

sys.path.append("/home/peb/.openclaw/workspace/flood-prediction-world/src")

from gis.models import (
    BoundingBox,
    SpatialReferenceSystem,
    DigitalTerrainModel,
    WaterSurfaceGeometry,
    WeatherParameters,
    SimulationConfig,
    SimulationResult,
    VectorFormat,
    RasterFormat,
)


class TestBoundingBox:
    """Test cases for BoundingBox class."""

    def test_initialization(self):
        """Test bounding box initialization."""
        bbox = BoundingBox(min_x=0.0, min_y=0.0, max_x=100.0, max_y=100.0, epsg=4326)

        assert bbox.min_x == 0.0
        assert bbox.min_y == 0.0
        assert bbox.max_x == 100.0
        assert bbox.max_y == 100.0
        assert bbox.epsg == 4326

    def test_properties(self):
        """Test computed properties."""
        bbox = BoundingBox(0, 0, 100, 50, 4326)

        assert bbox.width == 100.0
        assert bbox.height == 50.0
        assert bbox.area == 5000.0
        assert bbox.center == (50.0, 25.0)

    def test_contains(self):
        """Test point containment."""
        bbox = BoundingBox(0, 0, 100, 100, 4326)

        # Point inside
        assert bbox.contains(50, 50) is True
        # Point on boundary
        assert bbox.contains(0, 0) is True
        assert bbox.contains(100, 100) is True
        # Point outside
        assert bbox.contains(150, 50) is False
        assert bbox.contains(50, 150) is False
        assert bbox.contains(-10, 50) is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        bbox = BoundingBox(0, 0, 100, 100, 4326)
        data = bbox.to_dict()

        assert data["min_x"] == 0.0
        assert data["max_x"] == 100.0
        assert data["epsg"] == 4326
        assert "width" in data
        assert "height" in data
        assert "center" in data


class TestSpatialReferenceSystem:
    """Test cases for SpatialReferenceSystem class."""

    def test_initialization_wgs84(self):
        """Test WGS84 initialization."""
        crs = SpatialReferenceSystem(epsg_code=4326)

        assert crs.epsg_code == 4326
        assert crs.name == "WGS 84"
        assert crs.units == "degrees"
        assert crs.is_geographic() is True
        assert crs.is_projected() is False

    def test_initialization_web_mercator(self):
        """Test Web Mercator initialization."""
        crs = SpatialReferenceSystem(epsg_code=3857)

        assert crs.epsg_code == 3857
        assert crs.name == "Web Mercator"
        assert crs.units == "meters"
        assert crs.is_geographic() is False
        assert crs.is_projected() is True

    def test_initialization_custom(self):
        """Test custom CRS initialization."""
        crs = SpatialReferenceSystem(epsg_code=9999, name="Custom CRS", units="meters")

        assert crs.epsg_code == 9999
        assert crs.name == "Custom CRS"
        assert crs.units == "meters"

    def test_to_dict(self):
        """Test dictionary conversion."""
        crs = SpatialReferenceSystem(4326)
        data = crs.to_dict()

        assert data["epsg_code"] == 4326
        assert data["name"] == "WGS 84"
        assert "units" in data


class TestDigitalTerrainModel:
    """Test cases for DigitalTerrainModel class."""

    @pytest.fixture
    def sample_dtm(self):
        """Create a sample DTM for testing."""
        # Create 10x10 elevation grid
        elevation = np.array(
            [
                [10, 12, 14, 16, 18, 20, 22, 24, 26, 28],
                [12, 14, 16, 18, 20, 22, 24, 26, 28, 30],
                [14, 16, 18, 20, 22, 24, 26, 28, 30, 32],
                [16, 18, 20, 22, 24, 26, 28, 30, 32, 34],
                [18, 20, 22, 24, 26, 28, 30, 32, 34, 36],
                [20, 22, 24, 26, 28, 30, 32, 34, 36, 38],
                [22, 24, 26, 28, 30, 32, 34, 36, 38, 40],
                [24, 26, 28, 30, 32, 34, 36, 38, 40, 42],
                [26, 28, 30, 32, 34, 36, 38, 40, 42, 44],
                [28, 30, 32, 34, 36, 38, 40, 42, 44, 46],
            ],
            dtype=np.float32,
        )

        bounds = BoundingBox(
            min_x=0,
            min_y=0,
            max_x=100,
            max_y=100,
            epsg=32633,  # UTM 33N
        )

        crs = SpatialReferenceSystem(epsg_code=32633)

        return DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=(10.0, 10.0),
            crs=crs,
            nodata_value=-9999.0,
        )

    def test_initialization(self, sample_dtm):
        """Test DTM initialization."""
        assert sample_dtm.shape == (10, 10)
        assert sample_dtm.height == 10
        assert sample_dtm.width == 10
        assert sample_dtm.resolution == (10.0, 10.0)

    def test_elevation_stats(self, sample_dtm):
        """Test elevation statistics."""
        assert sample_dtm.min_elevation == 10.0
        assert sample_dtm.max_elevation == 46.0
        assert abs(sample_dtm.mean_elevation - 28.0) < 1.0

    def test_get_elevation_at(self, sample_dtm):
        """Test elevation interpolation."""
        # Test exact grid point
        elev = sample_dtm.get_elevation_at(5, 95)
        assert elev is not None

        # Test out of bounds
        elev = sample_dtm.get_elevation_at(150, 50)
        assert elev is None

        elev = sample_dtm.get_elevation_at(50, 150)
        assert elev is None

    def test_invalid_initialization(self):
        """Test invalid DTM initialization."""
        # Wrong dimensions
        with pytest.raises(ValueError):
            DigitalTerrainModel(
                elevation_data=np.array([1, 2, 3]),  # 1D array
                bounds=BoundingBox(0, 0, 100, 100, 4326),
                resolution=(10, 10),
                crs=SpatialReferenceSystem(4326),
            )

    def test_to_dict(self, sample_dtm):
        """Test dictionary conversion."""
        data = sample_dtm.to_dict()

        assert "shape" in data
        assert "min_elevation" in data
        assert "max_elevation" in data
        assert "bounds" in data
        assert "crs" in data


class TestWaterSurfaceGeometry:
    """Test cases for WaterSurfaceGeometry class."""

    @pytest.fixture
    def sample_geometry(self):
        """Create a sample water surface geometry."""
        # Simple triangle mesh (2 triangles forming a quad)
        vertices = np.array(
            [
                [0, 0, 1.0],  # v0
                [1, 0, 1.2],  # v1
                [1, 1, 1.1],  # v2
                [0, 1, 1.3],  # v3
            ],
            dtype=np.float32,
        )

        faces = np.array(
            [
                [0, 1, 2],  # Triangle 1
                [0, 2, 3],  # Triangle 2
            ],
            dtype=np.int32,
        )

        uvs = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)

        return WaterSurfaceGeometry(vertices=vertices, faces=faces, uvs=uvs)

    def test_initialization(self, sample_geometry):
        """Test geometry initialization."""
        assert sample_geometry.vertex_count == 4
        assert sample_geometry.face_count == 2
        assert sample_geometry.vertices.shape == (4, 3)
        assert sample_geometry.faces.shape == (2, 3)

    def test_calculate_normals(self, sample_geometry):
        """Test normal calculation."""
        normals = sample_geometry.calculate_normals()

        assert normals.shape == (2, 3)  # One normal per face
        # Normals should be unit vectors
        norms = np.linalg.norm(normals, axis=1)
        assert np.allclose(norms, 1.0)

    def test_to_threejs_format(self, sample_geometry):
        """Test Three.js export."""
        data = sample_geometry.to_threejs_format()

        assert "vertices" in data
        assert "indices" in data
        assert "uvs" in data
        assert "vertex_count" in data
        assert "face_count" in data
        assert data["vertex_count"] == 4
        assert data["face_count"] == 2

    def test_invalid_initialization(self):
        """Test invalid geometry initialization."""
        # Wrong vertex dimensions
        with pytest.raises(ValueError):
            WaterSurfaceGeometry(
                vertices=np.array([[1, 2], [3, 4]]),  # 2D instead of 3D
                faces=np.array([[0, 1, 2]]),
            )

        # Wrong face dimensions
        with pytest.raises(ValueError):
            WaterSurfaceGeometry(
                vertices=np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1]]),
                faces=np.array([[0, 1]]),  # 2 vertices instead of 3
            )


class TestWeatherParameters:
    """Test cases for WeatherParameters class."""

    def test_default_initialization(self):
        """Test default weather parameters."""
        weather = WeatherParameters()

        assert weather.rainfall_intensity == 0.0
        assert weather.rainfall_duration == 0.0
        assert weather.wind_speed == 0.0
        assert weather.temperature == 20.0
        assert weather.humidity == 0.5

    def test_custom_initialization(self):
        """Test custom weather parameters."""
        weather = WeatherParameters(
            rainfall_intensity=50.0,
            rainfall_duration=2.0,
            wind_speed=10.0,
            wind_direction=45.0,
            temperature=25.0,
            humidity=0.8,
        )

        assert weather.rainfall_intensity == 50.0
        assert weather.rainfall_duration == 2.0
        assert weather.total_rainfall == 100.0
        assert weather.wind_speed == 10.0
        assert weather.wind_direction == 45.0

    def test_total_rainfall(self):
        """Test total rainfall calculation."""
        weather = WeatherParameters(rainfall_intensity=25.0, rainfall_duration=3.0)

        assert weather.total_rainfall == 75.0

    def test_to_dict(self):
        """Test dictionary conversion."""
        weather = WeatherParameters(rainfall_intensity=30.0, rainfall_duration=1.5)
        data = weather.to_dict()

        assert data["rainfall_intensity"] == 30.0
        assert data["total_rainfall"] == 45.0
        assert "timestamp" in data


class TestSimulationConfig:
    """Test cases for SimulationConfig class."""

    def test_default_initialization(self):
        """Test default simulation configuration."""
        config = SimulationConfig()

        assert config.time_step == 1.0
        assert config.total_time == 3600.0
        assert config.output_interval == 60.0
        assert config.gravity == 9.81
        assert config.use_gpu is False

    def test_custom_initialization(self):
        """Test custom simulation configuration."""
        config = SimulationConfig(
            time_step=0.5,
            total_time=7200.0,
            output_interval=30.0,
            gravity=9.8,
            use_gpu=True,
        )

        assert config.time_step == 0.5
        assert config.total_time == 7200.0
        assert config.output_interval == 30.0
        assert config.gravity == 9.8
        assert config.use_gpu is True

    def test_num_outputs(self):
        """Test number of outputs calculation."""
        config = SimulationConfig(total_time=3600.0, output_interval=60.0)

        assert config.to_dict()["num_outputs"] == 60

    def test_to_dict(self):
        """Test dictionary conversion."""
        config = SimulationConfig()
        data = config.to_dict()

        assert "time_step" in data
        assert "total_time" in data
        assert "num_outputs" in data
        assert "gravity" in data


class TestSimulationResult:
    """Test cases for SimulationResult class."""

    def test_initialization(self):
        """Test result initialization."""
        result = SimulationResult()

        assert len(result.water_depth) == 0
        assert len(result.water_surface) == 0
        assert len(result.timestamps) == 0
        assert result.max_water_depth == 0.0

    def test_add_timestep(self):
        """Test adding simulation timesteps."""
        result = SimulationResult()

        # Add first timestep
        depth1 = np.array([[0, 0.5], [1.0, 0.3]])
        surface1 = WaterSurfaceGeometry(
            vertices=np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1]]),
            faces=np.array([[0, 1, 2]]),
        )
        result.add_timestep(depth1, surface1, 0.0)

        # Add second timestep with higher depth
        depth2 = np.array([[0, 1.5], [2.0, 1.3]])
        surface2 = WaterSurfaceGeometry(
            vertices=np.array([[0, 0, 2], [1, 0, 2], [1, 1, 2]]),
            faces=np.array([[0, 1, 2]]),
        )
        result.add_timestep(depth2, surface2, 60.0)

        assert len(result.timestamps) == 2
        assert result.max_water_depth == 2.0

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = SimulationResult()
        result.max_water_depth = 3.5
        result.flooded_area = 1000.0

        data = result.to_dict()

        assert data["num_timesteps"] == 0
        assert data["max_water_depth"] == 3.5
        assert data["flooded_area"] == 1000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
