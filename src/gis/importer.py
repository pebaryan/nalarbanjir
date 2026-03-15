"""GIS file import and processing module.

This module provides functionality for importing GIS data in various formats
including GeoTIFF, Shapefile, and GeoJSON.
"""

import logging
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import numpy as np

# Import the models
from .models import (
    DigitalTerrainModel,
    BoundingBox,
    SpatialReferenceSystem,
    VectorFormat,
    RasterFormat,
)

logger = logging.getLogger(__name__)


class GISImportError(Exception):
    """Custom exception for GIS import errors."""

    pass


class GISImporter:
    """Main class for importing GIS data files.

    Supports multiple formats:
    - Raster: GeoTIFF, ASCII Grid
    - Vector: Shapefile, GeoJSON, GeoPackage

    Usage:
        importer = GISImporter()
        dtm = importer.import_raster("path/to/dtm.tif")
        vectors = importer.import_vector("path/to/rivers.shp")
    """

    def __init__(self):
        """Initialize the GIS importer."""
        self.supported_raster_formats = [".tif", ".tiff", ".asc", ".h5", ".nc"]
        self.supported_vector_formats = [".shp", ".geojson", ".json", ".gpkg", ".kml"]

    def import_raster(
        self, filepath: Union[str, Path], target_crs: Optional[int] = None
    ) -> DigitalTerrainModel:
        """Import raster data (DTM/DSM).

        Args:
            filepath: Path to raster file
            target_crs: Optional target CRS (EPSG code) for reprojection

        Returns:
            DigitalTerrainModel object

        Raises:
            GISImportError: If file cannot be imported
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise GISImportError(f"File not found: {filepath}")

        # Check format
        suffix = filepath.suffix.lower()
        if suffix not in self.supported_raster_formats:
            raise GISImportError(f"Unsupported raster format: {suffix}")

        logger.info(f"Importing raster file: {filepath}")

        try:
            if suffix in [".tif", ".tiff"]:
                return self._import_geotiff(filepath, target_crs)
            elif suffix == ".asc":
                return self._import_ascii_grid(filepath, target_crs)
            else:
                raise GISImportError(f"Raster format not yet implemented: {suffix}")
        except Exception as e:
            raise GISImportError(f"Failed to import raster: {e}")

    def _import_geotiff(
        self, filepath: Path, target_crs: Optional[int] = None
    ) -> DigitalTerrainModel:
        """Import GeoTIFF file.

        Args:
            filepath: Path to GeoTIFF file
            target_crs: Optional target CRS

        Returns:
            DigitalTerrainModel
        """
        try:
            import rasterio
            from rasterio.transform import from_bounds
        except ImportError:
            raise GISImportError("rasterio package required for GeoTIFF import")

        with rasterio.open(filepath) as src:
            # Read elevation data
            elevation = src.read(1)  # Read first band

            # Get CRS
            crs = src.crs
            epsg_code = crs.to_epsg() if crs else 4326

            # Get bounds
            bounds = src.bounds
            bbox = BoundingBox(
                min_x=bounds.left,
                min_y=bounds.bottom,
                max_x=bounds.right,
                max_y=bounds.top,
                epsg=epsg_code,
            )

            # Get resolution
            resolution = (src.res[0], src.res[1])

            # Get nodata value
            nodata = src.nodata if src.nodata is not None else -9999.0

            # Reproject if needed
            if target_crs and target_crs != epsg_code:
                elevation, bbox = self._reproject_raster(
                    elevation, src.transform, epsg_code, target_crs
                )
                epsg_code = target_crs

            # Create CRS object
            crs_obj = SpatialReferenceSystem(epsg_code=epsg_code)

            # Create DTM
            dtm = DigitalTerrainModel(
                elevation_data=elevation.astype(np.float32),
                bounds=bbox,
                resolution=resolution,
                crs=crs_obj,
                nodata_value=float(nodata),
                metadata={
                    "source_file": str(filepath),
                    "bands": src.count,
                    "data_type": str(src.dtypes[0]),
                    "width": src.width,
                    "height": src.height,
                },
            )

            logger.info(f"Successfully imported GeoTIFF: {src.width}x{src.height}")
            return dtm

    def _import_ascii_grid(
        self, filepath: Path, target_crs: Optional[int] = None
    ) -> DigitalTerrainModel:
        """Import ASCII Grid file (ESRI format).

        Args:
            filepath: Path to ASCII grid file
            target_crs: Optional target CRS

        Returns:
            DigitalTerrainModel
        """
        try:
            import rasterio
        except ImportError:
            raise GISImportError("rasterio package required for ASCII grid import")

        # rasterio can read ASCII grids directly
        with rasterio.open(filepath) as src:
            elevation = src.read(1)

            # ASCII grids don't always have CRS, default to None
            epsg_code = 4326  # Default to WGS84

            bounds = src.bounds
            bbox = BoundingBox(
                min_x=bounds.left,
                min_y=bounds.bottom,
                max_x=bounds.right,
                max_y=bounds.top,
                epsg=epsg_code,
            )

            resolution = (src.res[0], src.res[1])
            nodata = src.nodata if src.nodata is not None else -9999.0

            crs_obj = SpatialReferenceSystem(epsg_code=epsg_code)

            dtm = DigitalTerrainModel(
                elevation_data=elevation.astype(np.float32),
                bounds=bbox,
                resolution=resolution,
                crs=crs_obj,
                nodata_value=float(nodata),
                metadata={"source_file": str(filepath), "format": "ASCII Grid"},
            )

            logger.info(f"Successfully imported ASCII Grid: {src.width}x{src.height}")
            return dtm

    def _reproject_raster(
        self, data: np.ndarray, transform, src_crs: int, dst_crs: int
    ) -> tuple:
        """Reproject raster data to new CRS.

        Args:
            data: Raster data array
            transform: Affine transform
            src_crs: Source CRS EPSG code
            dst_crs: Destination CRS EPSG code

        Returns:
            Tuple of (reprojected_data, new_bounds)
        """
        try:
            from rasterio.warp import reproject, Resampling, calculate_default_transform
            import rasterio
        except ImportError:
            raise GISImportError("rasterio required for reprojection")

        # Calculate new transform and dimensions
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            dst_crs,
            data.shape[1],
            data.shape[0],
            *rasterio.transform.array_bounds(data.shape[0], data.shape[1], transform),
        )

        # Create destination array
        dst_data = np.empty((dst_height, dst_width), dtype=data.dtype)

        # Reproject
        reproject(
            source=data,
            destination=dst_data,
            src_transform=transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
        )

        # Calculate new bounds
        bounds = rasterio.transform.array_bounds(dst_height, dst_width, dst_transform)
        new_bbox = BoundingBox(
            min_x=bounds[0],
            min_y=bounds[1],
            max_x=bounds[2],
            max_y=bounds[3],
            epsg=dst_crs,
        )

        return dst_data, new_bbox

    def import_vector(
        self, filepath: Union[str, Path], target_crs: Optional[int] = None
    ) -> "VectorData":
        """Import vector data (Shapefile, GeoJSON, etc.).

        Args:
            filepath: Path to vector file
            target_crs: Optional target CRS

        Returns:
            VectorData object

        Raises:
            GISImportError: If file cannot be imported
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise GISImportError(f"File not found: {filepath}")

        suffix = filepath.suffix.lower()
        if suffix not in self.supported_vector_formats:
            raise GISImportError(f"Unsupported vector format: {suffix}")

        logger.info(f"Importing vector file: {filepath}")

        try:
            return self._import_with_geopandas(filepath, target_crs)
        except Exception as e:
            raise GISImportError(f"Failed to import vector: {e}")

    def _import_with_geopandas(
        self, filepath: Path, target_crs: Optional[int] = None
    ) -> "VectorData":
        """Import vector data using GeoPandas.

        Args:
            filepath: Path to vector file
            target_crs: Optional target CRS

        Returns:
            VectorData object
        """
        try:
            import geopandas as gpd
        except ImportError:
            raise GISImportError("geopandas package required for vector import")

        # Read file
        gdf = gpd.read_file(filepath)

        # Reproject if needed
        if target_crs:
            if gdf.crs is None:
                logger.warning("Vector file has no CRS, assuming WGS84")
                gdf = gdf.set_crs(epsg=4326)
            gdf = gdf.to_crs(epsg=target_crs)

        # Create VectorData object
        vector_data = VectorData(
            geodataframe=gdf,
            source_file=str(filepath),
            crs=target_crs or (gdf.crs.to_epsg() if gdf.crs else 4326),
        )

        logger.info(f"Successfully imported vector: {len(gdf)} features")
        return vector_data

    def get_file_info(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """Get information about a GIS file without fully loading it.

        Args:
            filepath: Path to file

        Returns:
            Dictionary with file information
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return {"error": "File not found"}

        suffix = filepath.suffix.lower()
        info = {
            "filepath": str(filepath),
            "filename": filepath.name,
            "size_mb": filepath.stat().st_size / (1024 * 1024),
            "format": suffix,
        }

        try:
            if suffix in [".tif", ".tiff"]:
                import rasterio

                with rasterio.open(filepath) as src:
                    info.update(
                        {
                            "type": "raster",
                            "width": src.width,
                            "height": src.height,
                            "bands": src.count,
                            "crs": str(src.crs),
                            "resolution": src.res,
                            "bounds": {
                                "left": src.bounds.left,
                                "bottom": src.bounds.bottom,
                                "right": src.bounds.right,
                                "top": src.bounds.top,
                            },
                        }
                    )
            elif suffix in [".shp", ".geojson", ".gpkg"]:
                import geopandas as gpd

                gdf = gpd.read_file(filepath, rows=0)  # Read only schema
                info.update(
                    {
                        "type": "vector",
                        "geometry_type": str(gdf.geom_type.unique()),
                        "crs": str(gdf.crs),
                        "columns": list(gdf.columns),
                    }
                )
        except Exception as e:
            info["error"] = str(e)

        return info


class VectorData:
    """Container for vector GIS data.

    Attributes:
        geodataframe: GeoPandas GeoDataFrame
        source_file: Original source file path
        crs: Coordinate reference system (EPSG code)
    """

    def __init__(self, geodataframe, source_file: str, crs: int):
        """Initialize vector data container."""
        self.geodataframe = geodataframe
        self.source_file = source_file
        self.crs = crs
        self._validate()

    def _validate(self):
        """Validate the vector data."""
        if self.geodataframe is None or len(self.geodataframe) == 0:
            logger.warning("Vector data is empty")

    @property
    def feature_count(self) -> int:
        """Get number of features."""
        return len(self.geodataframe)

    @property
    def geometry_types(self) -> List[str]:
        """Get unique geometry types."""
        return self.geodataframe.geom_type.unique().tolist()

    @property
    def bounds(self) -> BoundingBox:
        """Get bounding box."""
        bounds = self.geodataframe.total_bounds
        return BoundingBox(
            min_x=bounds[0],
            min_y=bounds[1],
            max_x=bounds[2],
            max_y=bounds[3],
            epsg=self.crs,
        )

    def filter_by_attribute(self, column: str, value) -> "VectorData":
        """Filter features by attribute value.

        Args:
            column: Column name
            value: Value to filter by

        Returns:
            Filtered VectorData
        """
        filtered = self.geodataframe[self.geodataframe[column] == value]
        return VectorData(filtered, self.source_file, self.crs)

    def filter_by_bounds(self, bbox: BoundingBox) -> "VectorData":
        """Filter features by bounding box.

        Args:
            bbox: Bounding box

        Returns:
            Filtered VectorData
        """
        from shapely.geometry import box

        # Create bounding box polygon
        bbox_poly = box(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)

        # Spatial filter
        filtered = self.geodataframe[self.geodataframe.intersects(bbox_poly)]
        return VectorData(filtered, self.source_file, self.crs)

    def to_geojson(self) -> Dict:
        """Export to GeoJSON format.

        Returns:
            GeoJSON dictionary
        """
        return self.geodataframe.to_geo_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary summary."""
        return {
            "feature_count": self.feature_count,
            "geometry_types": self.geometry_types,
            "crs": self.crs,
            "source_file": self.source_file,
            "bounds": self.bounds.to_dict(),
            "columns": list(self.geodataframe.columns),
        }
