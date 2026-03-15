"""Tests for GIS importer module.

Tests for importing GeoTIFF, Shapefile, and GeoJSON files.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import os

import sys

sys.path.append("/home/peb/.openclaw/workspace/flood-prediction-world/src")

from gis.importer import GISImporter, VectorData, GISImportError
from gis.models import DigitalTerrainModel, BoundingBox, SpatialReferenceSystem


class TestGISImporter:
    """Test cases for GISImporter class."""

    @pytest.fixture
    def importer(self):
        """Create GISImporter instance."""
        return GISImporter()

    def test_initialization(self, importer):
        """Test importer initialization."""
        assert ".tif" in importer.supported_raster_formats
        assert ".shp" in importer.supported_vector_formats

    def test_import_nonexistent_file(self, importer):
        """Test importing non-existent file."""
        with pytest.raises(GISImportError) as exc_info:
            importer.import_raster("/nonexistent/file.tif")

        assert "File not found" in str(exc_info.value)

    def test_unsupported_raster_format(self, importer):
        """Test importing unsupported raster format."""
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(GISImportError) as exc_info:
                importer.import_raster(tmp_path)

            assert "Unsupported raster format" in str(exc_info.value)
        finally:
            os.unlink(tmp_path)

    def test_unsupported_vector_format(self, importer):
        """Test importing unsupported vector format."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(GISImportError) as exc_info:
                importer.import_vector(tmp_path)

            assert "Unsupported vector format" in str(exc_info.value)
        finally:
            os.unlink(tmp_path)

    def test_get_file_info_nonexistent(self, importer):
        """Test getting info for non-existent file."""
        info = importer.get_file_info("/nonexistent/file.tif")

        assert "error" in info
        assert info["error"] == "File not found"

    def test_get_file_info_temp_file(self, importer):
        """Test getting info for temporary file."""
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp.write(b"dummy data")
            tmp_path = tmp.name

        try:
            info = importer.get_file_info(tmp_path)

            assert info["filepath"] == tmp_path
            assert info["filename"] == Path(tmp_path).name
            assert info["format"] == ".tif"
            assert "size_mb" in info
        finally:
            os.unlink(tmp_path)


class TestGISImporterIntegration:
    """Integration tests for GISImporter with real data."""

    @pytest.fixture
    def sample_geotiff(self, tmp_path):
        """Create a sample GeoTIFF file for testing."""
        try:
            import rasterio
            from rasterio.transform import from_origin
        except ImportError:
            pytest.skip("rasterio not installed")

        filepath = tmp_path / "test_elevation.tif"

        # Create sample elevation data
        elevation = np.random.rand(50, 50).astype(np.float32) * 100

        # GeoTIFF parameters
        transform = from_origin(0, 1000, 20, 20)  # 20m resolution

        with rasterio.open(
            filepath,
            "w",
            driver="GTiff",
            height=50,
            width=50,
            count=1,
            dtype=elevation.dtype,
            crs="EPSG:32633",
            transform=transform,
            nodata=-9999,
        ) as dst:
            dst.write(elevation, 1)

        return filepath

    @pytest.fixture
    def sample_shapefile(self, tmp_path):
        """Create a sample Shapefile for testing."""
        try:
            import geopandas as gpd
            from shapely.geometry import Point
        except ImportError:
            pytest.skip("geopandas not installed")

        filepath = tmp_path / "test_points.shp"

        # Create sample points
        data = {
            "name": ["Point1", "Point2", "Point3"],
            "value": [10, 20, 30],
            "geometry": [Point(10, 10), Point(20, 20), Point(30, 30)],
        }

        gdf = gpd.GeoDataFrame(data, crs="EPSG:32633")
        gdf.to_file(filepath)

        return filepath

    @pytest.fixture
    def sample_geojson(self, tmp_path):
        """Create a sample GeoJSON file for testing."""
        try:
            import geopandas as gpd
            from shapely.geometry import Polygon
        except ImportError:
            pytest.skip("geopandas not installed")

        filepath = tmp_path / "test_areas.geojson"

        # Create sample polygons
        data = {
            "name": ["Area1", "Area2"],
            "type": ["residential", "commercial"],
            "geometry": [
                Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
                Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]),
            ],
        }

        gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
        gdf.to_file(filepath, driver="GeoJSON")

        return filepath

    def test_import_geotiff(self, sample_geotiff):
        """Test importing GeoTIFF file."""
        importer = GISImporter()

        dtm = importer.import_raster(sample_geotiff)

        assert isinstance(dtm, DigitalTerrainModel)
        assert dtm.shape == (50, 50)
        assert dtm.crs.epsg_code == 32633
        assert dtm.resolution == (20.0, 20.0)

    def test_import_geotiff_with_reprojection(self, sample_geotiff):
        """Test importing GeoTIFF with CRS reprojection."""
        importer = GISImporter()

        # Reproject to Web Mercator
        dtm = importer.import_raster(sample_geotiff, target_crs=3857)

        assert isinstance(dtm, DigitalTerrainModel)
        assert dtm.crs.epsg_code == 3857

    def test_get_file_info_geotiff(self, sample_geotiff):
        """Test getting info for GeoTIFF file."""
        importer = GISImporter()

        info = importer.get_file_info(sample_geotiff)

        assert info["type"] == "raster"
        assert info["width"] == 50
        assert info["height"] == 50
        assert info["bands"] == 1
        assert "crs" in info
        assert "bounds" in info

    def test_import_shapefile(self, sample_shapefile):
        """Test importing Shapefile."""
        importer = GISImporter()

        vector = importer.import_vector(sample_shapefile)

        assert isinstance(vector, VectorData)
        assert vector.feature_count == 3
        assert vector.crs == 32633

    def test_import_geojson(self, sample_geojson):
        """Test importing GeoJSON file."""
        importer = GISImporter()

        vector = importer.import_vector(sample_geojson)

        assert isinstance(vector, VectorData)
        assert vector.feature_count == 2
        assert vector.crs == 4326

    def test_import_geojson_with_reprojection(self, sample_geojson):
        """Test importing GeoJSON with CRS reprojection."""
        importer = GISImporter()

        # Reproject to UTM
        vector = importer.import_vector(sample_geojson, target_crs=32633)

        assert isinstance(vector, VectorData)
        assert vector.crs == 32633


class TestVectorData:
    """Test cases for VectorData class."""

    @pytest.fixture
    def sample_vector_data(self):
        """Create sample vector data."""
        try:
            import geopandas as gpd
            from shapely.geometry import Point, Polygon
        except ImportError:
            pytest.skip("geopandas not installed")

        data = {
            "id": [1, 2, 3, 4],
            "category": ["A", "B", "A", "B"],
            "value": [10.5, 20.3, 15.7, 8.2],
            "geometry": [
                Point(0, 0),
                Point(10, 10),
                Polygon([(5, 5), (15, 5), (15, 15), (5, 15)]),
                Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]),
            ],
        }

        gdf = gpd.GeoDataFrame(data, crs="EPSG:32633")

        return VectorData(geodataframe=gdf, source_file="/test/data.shp", crs=32633)

    def test_initialization(self, sample_vector_data):
        """Test VectorData initialization."""
        assert sample_vector_data.feature_count == 4
        assert sample_vector_data.crs == 32633
        assert sample_vector_data.source_file == "/test/data.shp"

    def test_geometry_types(self, sample_vector_data):
        """Test getting geometry types."""
        types = sample_vector_data.geometry_types

        assert "Point" in types
        assert "Polygon" in types

    def test_bounds(self, sample_vector_data):
        """Test getting bounds."""
        bounds = sample_vector_data.bounds

        assert isinstance(bounds, BoundingBox)
        assert bounds.epsg == 32633
        assert bounds.min_x == 0
        assert bounds.min_y == 0

    def test_filter_by_attribute(self, sample_vector_data):
        """Test filtering by attribute."""
        filtered = sample_vector_data.filter_by_attribute("category", "A")

        assert isinstance(filtered, VectorData)
        assert filtered.feature_count == 2

    def test_filter_by_bounds(self, sample_vector_data):
        """Test filtering by bounds."""
        bbox = BoundingBox(0, 0, 15, 15, 32633)
        filtered = sample_vector_data.filter_by_bounds(bbox)

        assert isinstance(filtered, VectorData)
        assert filtered.feature_count >= 2  # At least 2 features should be in bounds

    def test_to_dict(self, sample_vector_data):
        """Test dictionary conversion."""
        data = sample_vector_data.to_dict()

        assert "feature_count" in data
        assert "geometry_types" in data
        assert "crs" in data
        assert "bounds" in data
        assert "columns" in data
        assert data["feature_count"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
