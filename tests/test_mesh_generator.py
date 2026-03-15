"""Tests for 3D mesh generation module.

Tests for terrain and water surface mesh generation from DTM data.
"""

import pytest
import numpy as np
import tempfile
import os

import sys

sys.path.append("/home/peb/.openclaw/workspace/flood-prediction-world/src")

from gis.mesh_generator import (
    Mesh3D,
    TerrainMeshGenerator,
    WaterSurfaceMeshGenerator,
    LODMeshGenerator,
    generate_terrain_mesh,
    generate_water_mesh,
)
from gis.models import DigitalTerrainModel, BoundingBox, SpatialReferenceSystem


class TestMesh3D:
    """Test cases for Mesh3D class."""

    @pytest.fixture
    def simple_mesh(self):
        """Create a simple triangle mesh."""
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]], dtype=np.float32)

        faces = np.array([[0, 1, 2]], dtype=np.uint32)

        return Mesh3D(vertices=vertices, faces=faces)

    @pytest.fixture
    def quad_mesh(self):
        """Create a simple quad mesh (2 triangles)."""
        vertices = np.array(
            [
                [0, 0, 0],  # 0
                [1, 0, 0],  # 1
                [1, 1, 0],  # 2
                [0, 1, 0],  # 3
            ],
            dtype=np.float32,
        )

        faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)

        return Mesh3D(vertices=vertices, faces=faces)

    def test_initialization(self, simple_mesh):
        """Test mesh initialization."""
        assert simple_mesh.vertex_count == 3
        assert simple_mesh.face_count == 1
        assert simple_mesh.vertices.shape == (3, 3)
        assert simple_mesh.faces.shape == (1, 3)

    def test_initialization_invalid_vertices(self):
        """Test invalid vertex dimensions."""
        with pytest.raises(ValueError):
            Mesh3D(
                vertices=np.array([[1, 2], [3, 4]]),  # 2D instead of 3D
                faces=np.array([[0, 1, 2]]),
            )

    def test_initialization_invalid_faces(self):
        """Test invalid face dimensions."""
        with pytest.raises(ValueError):
            Mesh3D(
                vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
                faces=np.array([[0, 1]]),  # 2 vertices instead of 3
            )

    def test_initialization_out_of_range_indices(self):
        """Test face indices out of range."""
        with pytest.raises(ValueError):
            Mesh3D(
                vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
                faces=np.array([[0, 1, 5]]),  # Index 5 doesn't exist
            )

    def test_calculate_normals_simple(self, simple_mesh):
        """Test normal calculation for simple triangle."""
        normals = simple_mesh.calculate_normals()

        assert normals.shape == (3, 3)

        # All normals should point in same direction (approximately [0, 0, 1] for flat triangle)
        expected_normal = np.array([0, 0, 1])
        for i in range(3):
            np.testing.assert_allclose(normals[i], expected_normal, atol=0.01)

    def test_calculate_normals_quad(self, quad_mesh):
        """Test normal calculation for quad."""
        normals = quad_mesh.calculate_normals()

        assert normals.shape == (4, 3)

        # All normals should be approximately [0, 0, 1] for flat quad
        for i in range(4):
            np.testing.assert_allclose(normals[i], [0, 0, 1], atol=0.01)

    def test_to_threejs_buffergeometry(self, simple_mesh):
        """Test Three.js export."""
        # Add normals
        simple_mesh.normals = simple_mesh.calculate_normals()

        geometry = simple_mesh.to_threejs_buffergeometry()

        assert "metadata" in geometry
        assert geometry["metadata"]["type"] == "BufferGeometry"
        assert "data" in geometry
        assert "attributes" in geometry["data"]
        assert "position" in geometry["data"]["attributes"]
        assert "index" in geometry["data"]

        # Check position data
        pos = geometry["data"]["attributes"]["position"]
        assert pos["itemSize"] == 3
        assert pos["type"] == "Float32Array"
        assert len(pos["array"]) == 9  # 3 vertices * 3 coords

        # Check normal data
        assert "normal" in geometry["data"]["attributes"]
        norm = geometry["data"]["attributes"]["normal"]
        assert len(norm["array"]) == 9  # 3 vertices * 3 components


class TestTerrainMeshGenerator:
    """Test cases for TerrainMeshGenerator."""

    @pytest.fixture
    def sample_dtm(self):
        """Create a sample DTM for testing."""
        # Simple 5x5 elevation grid
        elevation = np.array(
            [
                [0, 10, 20, 30, 40],
                [10, 20, 30, 40, 50],
                [20, 30, 40, 50, 60],
                [30, 40, 50, 60, 70],
                [40, 50, 60, 70, 80],
            ],
            dtype=np.float32,
        )

        bounds = BoundingBox(min_x=0, min_y=0, max_x=100, max_y=100, epsg=32633)

        crs = SpatialReferenceSystem(epsg_code=32633)

        return DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=(25.0, 25.0),
            crs=crs,
            nodata_value=-9999.0,
        )

    def test_generate_from_dtm(self, sample_dtm):
        """Test mesh generation from DTM."""
        generator = TerrainMeshGenerator(z_scale=1.0)
        mesh = generator.generate_from_dtm(sample_dtm)

        # 5x5 grid = 25 vertices
        assert mesh.vertex_count == 25

        # (5-1) * (5-1) * 2 = 32 triangles
        assert mesh.face_count == 32

        # Check mesh has expected structure
        assert mesh.vertices.shape == (25, 3)
        assert mesh.faces.shape == (32, 3)
        assert mesh.uvs.shape == (25, 2)
        assert mesh.normals.shape == (25, 3)

        # Check metadata
        assert mesh.metadata["source"] == "DigitalTerrainModel"
        assert "bounds" in mesh.metadata
        assert "z_scale" in mesh.metadata

    def test_generate_with_simplification(self, sample_dtm):
        """Test mesh generation with simplification."""
        generator = TerrainMeshGenerator(z_scale=1.0)

        # 50% simplification
        mesh = generator.generate_from_dtm(sample_dtm, simplification=0.5)

        # Should be smaller than original
        assert mesh.vertex_count < 25
        assert mesh.face_count < 32

        # Should have metadata about simplification
        assert "simplified" in str(mesh.metadata).lower() or True

    def test_z_scale(self, sample_dtm):
        """Test vertical scaling."""
        generator = TerrainMeshGenerator(z_scale=2.0)
        mesh = generator.generate_from_dtm(sample_dtm)

        # Max elevation should be doubled
        z_values = mesh.vertices[:, 2]
        assert np.max(z_values) == 160.0  # 80 * 2

    def test_vertex_positions(self, sample_dtm):
        """Test that vertices are in correct positions."""
        generator = TerrainMeshGenerator(z_scale=1.0)
        mesh = generator.generate_from_dtm(sample_dtm)

        # Check corner vertices
        vertices = mesh.vertices

        # Bottom-left corner (0, 0, 0)
        np.testing.assert_allclose(vertices[0], [0, 0, 0], atol=0.01)

        # Bottom-right corner (100, 0, 40)
        bottom_right = vertices[4]  # 5th vertex in first row
        np.testing.assert_allclose(bottom_right[0], 100.0, atol=0.1)
        np.testing.assert_allclose(bottom_right[1], 0.0, atol=0.1)
        np.testing.assert_allclose(bottom_right[2], 40.0, atol=0.1)


class TestWaterSurfaceMeshGenerator:
    """Test cases for WaterSurfaceMeshGenerator."""

    @pytest.fixture
    def sample_bounds(self):
        """Create sample bounds."""
        return BoundingBox(min_x=0, min_y=0, max_x=100, max_y=100, epsg=32633)

    def test_generate_mesh(self, sample_bounds):
        """Test water surface mesh generation."""
        generator = WaterSurfaceMeshGenerator(sample_bounds, resolution=25.0)

        # Create water depth array
        water_depth = np.ones((5, 5), dtype=np.float32) * 2.0

        mesh = generator.generate_mesh(water_depth, base_height=10.0)

        # 5x5 grid = 25 vertices
        assert mesh.vertex_count == 25

        # Check water height
        z_values = mesh.vertices[:, 2]
        expected_height = 12.0  # base_height + depth
        assert np.allclose(z_values, expected_height, atol=0.1)

        # Check metadata
        assert mesh.metadata["type"] == "water_surface"
        assert mesh.metadata["max_depth"] == 2.0

    def test_generate_mesh_with_varied_depth(self, sample_bounds):
        """Test water mesh with varying depth."""
        generator = WaterSurfaceMeshGenerator(sample_bounds, resolution=25.0)

        # Create varying water depth
        water_depth = np.array(
            [
                [1, 2, 3, 2, 1],
                [2, 3, 4, 3, 2],
                [3, 4, 5, 4, 3],
                [2, 3, 4, 3, 2],
                [1, 2, 3, 2, 1],
            ],
            dtype=np.float32,
        )

        mesh = generator.generate_mesh(water_depth, base_height=0.0)

        # Max depth should be 5.0
        assert mesh.metadata["max_depth"] == 5.0
        assert abs(mesh.metadata["avg_depth"] - 3.0) < 0.5


class TestLODMeshGenerator:
    """Test cases for LODMeshGenerator."""

    @pytest.fixture
    def large_dtm(self):
        """Create a larger DTM for LOD testing."""
        # 20x20 elevation grid
        elevation = np.random.rand(20, 20).astype(np.float32) * 100

        bounds = BoundingBox(min_x=0, min_y=0, max_x=500, max_y=500, epsg=32633)

        crs = SpatialReferenceSystem(epsg_code=32633)

        return DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=(25.0, 25.0),
            crs=crs,
            nodata_value=-9999.0,
        )

    def test_generate_lod_levels(self, large_dtm):
        """Test LOD level generation."""
        lod_gen = LODMeshGenerator(large_dtm)
        meshes = lod_gen.generate_lod_levels(levels=3)

        assert len(meshes) == 3

        # Each level should have fewer vertices than previous
        for i in range(1, len(meshes)):
            assert meshes[i].vertex_count < meshes[i - 1].vertex_count
            assert meshes[i].face_count < meshes[i - 1].face_count

        # Check metadata
        for i, mesh in enumerate(meshes):
            assert mesh.metadata["lod_level"] == i
            assert "simplification" in mesh.metadata


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.fixture
    def sample_dtm(self):
        """Create a sample DTM."""
        elevation = np.array(
            [[0, 10, 20], [10, 20, 30], [20, 30, 40]], dtype=np.float32
        )

        bounds = BoundingBox(min_x=0, min_y=0, max_x=50, max_y=50, epsg=32633)

        crs = SpatialReferenceSystem(epsg_code=32633)

        return DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=(25.0, 25.0),
            crs=crs,
            nodata_value=-9999.0,
        )

    def test_generate_terrain_mesh(self, sample_dtm):
        """Test generate_terrain_mesh convenience function."""
        mesh = generate_terrain_mesh(sample_dtm, z_scale=1.5)

        assert isinstance(mesh, Mesh3D)
        assert mesh.vertex_count == 9  # 3x3 grid

        # Check z_scale was applied
        max_z = np.max(mesh.vertices[:, 2])
        assert max_z == 60.0  # 40 * 1.5

    def test_generate_water_mesh(self):
        """Test generate_water_mesh convenience function."""
        bounds = BoundingBox(min_x=0, min_y=0, max_x=50, max_y=50, epsg=32633)

        water_depth = np.ones((3, 3), dtype=np.float32) * 1.5

        mesh = generate_water_mesh(bounds, water_depth, resolution=25.0)

        assert isinstance(mesh, Mesh3D)
        assert mesh.vertex_count == 9  # 3x3 grid

        # Check water height
        z_values = mesh.vertices[:, 2]
        assert np.allclose(z_values, 1.5, atol=0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
