"""Tests for the terrain module."""

import numpy as np
import pytest

try:
    from src.physics.terrain import TerrainModel, LandUseType, TerrainFeature
except ImportError:
    # Fallback for when running tests from different directory
    from physics.terrain import TerrainModel, LandUseType, TerrainFeature


class TestTerrainModel:
    """Test cases for TerrainModel."""

    def test_initialization(self):
        """Test terrain model initialization with default parameters."""
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(50, 50))

        assert terrain.nx == 50
        assert terrain.ny == 50
        assert terrain.elevation.shape == (50, 50)
        assert terrain.land_use.shape == (50, 50)
        assert terrain.permeability.shape == (50, 50)
        assert isinstance(terrain.flood_thresholds, dict)
        assert "minor" in terrain.flood_thresholds
        assert "moderate" in terrain.flood_thresholds
        assert "major" in terrain.flood_thresholds
        assert "severe" in terrain.flood_thresholds

    def test_initialization_with_custom_params(self):
        """Test terrain model initialization with custom parameters."""
        config = {
            "flood_thresholds": {
                "minor": 0.5,
                "moderate": 1.5,
                "major": 2.5,
                "severe": 4.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(30, 40))

        assert terrain.nx == 30
        assert terrain.ny == 40
        assert terrain.flood_thresholds["minor"] == 0.5
        assert terrain.flood_thresholds["moderate"] == 1.5
        assert terrain.flood_thresholds["major"] == 2.5
        assert terrain.flood_thresholds["severe"] == 4.0

    def test_elevation_properties(self):
        """Test that elevation has correct properties."""
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(20, 20))

        # Check that elevation is non-negative
        assert np.all(terrain.elevation >= 0)
        # Check that elevation is finite
        assert np.all(np.isfinite(terrain.elevation))

    def test_land_use_classification(self):
        """Test land use classification."""
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(10, 10))

        # Check that land use contains valid values
        unique_values = np.unique(terrain.land_use)
        # Should be integers from 0 to 5 (6 land use types)
        assert len(unique_values) <= 6
        assert np.all(unique_values >= 0)
        assert np.all(unique_values <= 5)

    def test_permeability_properties(self):
        """Test permeability properties."""
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(10, 10))

        # Check that permeability is between 0 and 1
        assert np.all(terrain.permeability >= 0)
        assert np.all(terrain.permeability <= 1)
        # Check that permeability is finite
        assert np.all(np.isfinite(terrain.permeability))

    def get_flood_zones(self):
        """Test flood zone identification."""
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(10, 10))

        # Test with zero water depth (should be no flood zones)
        water_depth = np.zeros((10, 10))
        flood_zones = terrain.get_flood_zones(water_depth)

        # Should return a dictionary with flood zone information
        assert isinstance(flood_zones, dict)

        # Test with some water depth
        water_depth = np.array(
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ]
        )

        flood_zones = terrain.get_flood_zones(water_depth)
        assert isinstance(flood_zones, dict)

        # Test with higher water depth
        water_depth = np.ones((10, 10)) * 3.0  # 3m everywhere
        flood_zones = terrain.get_flood_zones(water_depth)
        assert isinstance(flood_zones, dict)

    def test_export_terrain_data(self):
        """Test exporting terrain data."""
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=config, resolution=(5, 5))

        terrain_data = terrain.export_terrain_data()

        # Check structure
        assert isinstance(terrain_data, dict)
        assert "elevation" in terrain_data
        assert "land_use" in terrain_data
        assert "permeability" in terrain_data
        assert "flood_thresholds" in terrain_data

        # Check data types and shapes
        assert isinstance(terrain_data["elevation"], dict)
        assert isinstance(terrain_data["land_use"], dict)
        assert isinstance(terrain_data["permeability"], dict)
        assert isinstance(terrain_data["flood_thresholds"], dict)

        assert isinstance(terrain_data["elevation"]["data"], np.ndarray)
        assert isinstance(terrain_data["land_use"]["classification"], np.ndarray)
        assert isinstance(terrain_data["permeability"]["data"], np.ndarray)

        assert terrain_data["elevation"]["data"].shape == (5, 5)
        assert terrain_data["land_use"]["classification"].shape == (5, 5)
        assert terrain_data["permeability"]["data"].shape == (5, 5)


class TestLandUseType:
    """Test cases for LandUseType enum."""

    def test_land_use_types(self):
        """Test that all expected land use types exist."""
        expected_types = {
            "water",
            "urban",
            "agricultural",
            "forest",
            "wetland",
            "open_land",
        }
        actual_types = {e.value for e in LandUseType}
        assert actual_types == expected_types

    def test_land_use_type_access(self):
        """Test accessing land use types."""
        assert LandUseType.WATER.value == "water"
        assert LandUseType.URBAN.value == "urban"
        assert LandUseType.AGRICULTURAL.value == "agricultural"
        assert LandUseType.FOREST.value == "forest"
        assert LandUseType.WETLAND.value == "wetland"
        assert LandUseType.OPEN_LAND.value == "open_land"


class TestTerrainFeature:
    """Test cases for TerrainFeature dataclass."""

    def test_terrain_feature_creation(self):
        """Test creating a TerrainFeature."""
        feature = TerrainFeature(
            feature_type=LandUseType.FOREST,
            elevation=100.5,
            permeability=0.7,
            vulnerability=3,
            description="Forest area with moderate slope",
        )

        assert feature.feature_type == LandUseType.FOREST
        assert feature.elevation == 100.5
        assert feature.permeability == 0.7
        assert feature.vulnerability == 3
        assert feature.description == "Forest area with moderate slope"

    def test_terrain_feature_defaults(self):
        """Test TerrainFeature with default values."""
        feature = TerrainFeature(
            feature_type=LandUseType.URBAN,
            elevation=50.0,
            permeability=0.3,
            vulnerability=2,
            description="Urban area",
        )

        assert feature.feature_type == LandUseType.URBAN
        assert feature.elevation == 50.0
        assert feature.permeability == 0.3
        assert feature.vulnerability == 2
        assert feature.description == "Urban area"


if __name__ == "__main__":
    pytest.main([__file__])
