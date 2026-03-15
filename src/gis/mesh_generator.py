"""3D mesh generation module for GIS-based flood simulation.

This module provides functionality for converting DTM data into 3D meshes
optimized for Three.js visualization, including terrain and water surfaces.
"""

import logging
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

from .models import DigitalTerrainModel, WaterSurfaceGeometry, BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class Mesh3D:
    """3D mesh data structure compatible with Three.js.

    Attributes:
        vertices: Nx3 array of vertex positions (x, y, z)
        faces: Mx3 array of face indices (triangles)
        uvs: Optional Nx2 array of texture coordinates
        normals: Optional Nx3 array of vertex normals
        colors: Optional Nx3 array of vertex colors
        metadata: Additional mesh metadata
    """

    vertices: np.ndarray
    faces: np.ndarray
    uvs: Optional[np.ndarray] = None
    normals: Optional[np.ndarray] = None
    colors: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Validate mesh data."""
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("vertices must be Nx3 array")
        if self.faces.ndim != 2 or self.faces.shape[1] != 3:
            raise ValueError("faces must be Mx3 array")
        if np.any(self.faces >= len(self.vertices)):
            raise ValueError("face indices out of range")

    @property
    def vertex_count(self) -> int:
        """Get number of vertices."""
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        """Get number of faces."""
        return len(self.faces)

    def calculate_normals(self) -> np.ndarray:
        """Calculate per-vertex normals by averaging face normals.

        Returns:
            Nx3 array of vertex normals
        """
        # Initialize vertex normals
        normals = np.zeros_like(self.vertices)
        counts = np.zeros(len(self.vertices))

        # Calculate face normals and accumulate
        for face in self.faces:
            v0, v1, v2 = self.vertices[face]

            # Face normal
            edge1 = v1 - v0
            edge2 = v2 - v0
            face_normal = np.cross(edge1, edge2)

            # Normalize
            norm = np.linalg.norm(face_normal)
            if norm > 0:
                face_normal = face_normal / norm

                # Add to all vertices of this face
                for idx in face:
                    normals[idx] += face_normal
                    counts[idx] += 1

        # Average and normalize
        mask = counts > 0
        normals[mask] = normals[mask] / counts[mask][:, np.newaxis]

        # Normalize all normals
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normals = normals / norms

        return normals

    def to_threejs_buffergeometry(self) -> Dict[str, Any]:
        """Convert to Three.js BufferGeometry format.

        Returns:
            Dictionary with Three.js compatible data
        """
        geometry = {
            "metadata": {
                "version": 4.5,
                "type": "BufferGeometry",
                "generator": "FloodSimulationMeshGenerator",
            },
            "data": {
                "attributes": {
                    "position": {
                        "itemSize": 3,
                        "type": "Float32Array",
                        "array": self.vertices.flatten().tolist(),
                        "normalized": False,
                    }
                },
                "index": {
                    "type": "Uint32Array",
                    "array": self.faces.flatten().tolist(),
                },
            },
        }

        # Add UVs if present
        if self.uvs is not None:
            geometry["data"]["attributes"]["uv"] = {
                "itemSize": 2,
                "type": "Float32Array",
                "array": self.uvs.flatten().tolist(),
                "normalized": False,
            }

        # Add normals if present
        if self.normals is not None:
            geometry["data"]["attributes"]["normal"] = {
                "itemSize": 3,
                "type": "Float32Array",
                "array": self.normals.flatten().tolist(),
                "normalized": False,
            }

        # Add colors if present
        if self.colors is not None:
            geometry["data"]["attributes"]["color"] = {
                "itemSize": 3,
                "type": "Float32Array",
                "array": self.colors.flatten().tolist(),
                "normalized": False,
            }

        return geometry


class TerrainMeshGenerator:
    """Generator for creating 3D terrain meshes from DTM data.

    Example:
        dtm = importer.import_raster("dem.tif")
        generator = TerrainMeshGenerator()
        mesh = generator.generate_from_dtm(dtm)
        threejs_data = mesh.to_threejs_buffergeometry()
    """

    def __init__(self, z_scale: float = 1.0):
        """Initialize mesh generator.

        Args:
            z_scale: Vertical exaggeration factor for elevation
        """
        self.z_scale = z_scale

    def generate_from_dtm(
        self, dtm: DigitalTerrainModel, simplification: Optional[float] = None
    ) -> Mesh3D:
        """Generate 3D mesh from DTM.

        Args:
            dtm: Digital terrain model
            simplification: Optional simplification factor (0-1, lower = simpler)

        Returns:
            3D mesh
        """
        logger.info(f"Generating terrain mesh from DTM: {dtm.shape}")

        elevation = dtm.elevation_data
        height, width = elevation.shape

        # Apply simplification if requested
        if simplification and simplification < 1.0:
            new_height = int(height * simplification)
            new_width = int(width * simplification)
            elevation = self._resample_elevation(elevation, new_height, new_width)
            height, width = elevation.shape
            logger.info(f"Simplified to: {height}x{width}")

        # Generate grid coordinates
        x_coords = np.linspace(dtm.bounds.min_x, dtm.bounds.max_x, width)
        y_coords = np.linspace(dtm.bounds.min_y, dtm.bounds.max_y, height)

        # Create mesh grid
        xx, yy = np.meshgrid(x_coords, y_coords)

        # Handle nodata values
        valid_mask = elevation != dtm.nodata_value
        z_values = np.where(
            valid_mask, elevation * self.z_scale, dtm.min_elevation * self.z_scale
        )

        # Calculate center offset to center terrain at origin
        center_x = (dtm.bounds.min_x + dtm.bounds.max_x) / 2
        center_y = (dtm.bounds.min_y + dtm.bounds.max_y) / 2
        min_z = np.min(z_values)

        # Center the coordinates
        xx_centered = xx - center_x
        yy_centered = yy - center_y
        z_centered = z_values - min_z

        # Create vertices (flattened grid)
        # Swap Y and Z for Three.js coordinate system (Y is up)
        vertices = np.column_stack(
            [xx_centered.flatten(), z_centered.flatten(), yy_centered.flatten()]
        ).astype(np.float32)

        # Generate faces (triangles)
        faces = self._generate_grid_faces(height, width)

        # Generate UVs for texture mapping
        uvs = self._generate_uvs(height, width)

        # Calculate normals
        mesh = Mesh3D(vertices=vertices, faces=faces, uvs=uvs)
        mesh.normals = mesh.calculate_normals()

        mesh.metadata = {
            "source": "DigitalTerrainModel",
            "bounds": dtm.bounds.to_dict(),
            "vertex_count": mesh.vertex_count,
            "face_count": mesh.face_count,
            "z_scale": self.z_scale,
        }

        logger.info(
            f"Generated mesh: {mesh.vertex_count} vertices, {mesh.face_count} faces"
        )
        return mesh

    def _resample_elevation(
        self, elevation: np.ndarray, new_height: int, new_width: int
    ) -> np.ndarray:
        """Resample elevation data to new dimensions.

        Args:
            elevation: Source elevation data
            new_height: Target height
            new_width: Target width

        Returns:
            Resampled elevation
        """
        from scipy.ndimage import zoom

        zoom_y = new_height / elevation.shape[0]
        zoom_x = new_width / elevation.shape[1]

        return zoom(elevation, (zoom_y, zoom_x), order=1)

    def _generate_grid_faces(self, height: int, width: int) -> np.ndarray:
        """Generate triangle faces for a regular grid.

        Args:
            height: Grid height in cells
            width: Grid width in cells

        Returns:
            Mx3 array of face indices
        """
        faces = []

        for row in range(height - 1):
            for col in range(width - 1):
                # Current cell corners
                i0 = row * width + col
                i1 = i0 + 1
                i2 = (row + 1) * width + col
                i3 = i2 + 1

                # Two triangles per cell
                faces.append([i0, i2, i1])  # Lower left triangle
                faces.append([i1, i2, i3])  # Upper right triangle

        return np.array(faces, dtype=np.uint32)

    def _generate_uvs(self, height: int, width: int) -> np.ndarray:
        """Generate UV texture coordinates.

        Args:
            height: Grid height
            width: Grid width

        Returns:
            Nx2 array of UV coordinates
        """
        u = np.linspace(0, 1, width)
        v = np.linspace(0, 1, height)

        uu, vv = np.meshgrid(u, v)

        return np.column_stack([uu.flatten(), vv.flatten()]).astype(np.float32)

    def apply_vertex_colors(
        self, mesh: Mesh3D, dtm: DigitalTerrainModel, colormap: str = "terrain"
    ) -> Mesh3D:
        """Apply vertex colors based on elevation.

        Args:
            mesh: 3D mesh
            dtm: Source DTM
            colormap: Matplotlib colormap name

        Returns:
            Mesh with vertex colors
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
        except ImportError:
            logger.warning("matplotlib not available for coloring")
            return mesh

        # Get elevations
        elevations = mesh.vertices[:, 2] / self.z_scale

        # Normalize to 0-1
        z_min = dtm.min_elevation
        z_max = dtm.max_elevation
        normalized = (elevations - z_min) / (z_max - z_min)
        normalized = np.clip(normalized, 0, 1)

        # Apply colormap
        cmap = plt.get_cmap(colormap)
        colors = cmap(normalized)[:, :3]  # Get RGB (drop alpha)

        mesh.colors = colors.astype(np.float32)
        return mesh


class WaterSurfaceMeshGenerator:
    """Generator for creating dynamic water surface meshes.

    Example:
        generator = WaterSurfaceMeshGenerator(bounds)
        mesh = generator.generate_mesh(water_depth=2.5)
    """

    def __init__(self, bounds: BoundingBox, resolution: float = 10.0):
        """Initialize water mesh generator.

        Args:
            bounds: Spatial bounds
            resolution: Grid resolution in CRS units
        """
        self.bounds = bounds
        self.resolution = resolution

        # Calculate grid dimensions
        self.width = int((bounds.max_x - bounds.min_x) / resolution) + 1
        self.height = int((bounds.max_y - bounds.min_y) / resolution) + 1

        logger.info(f"Water mesh grid: {self.width}x{self.height}")

    def generate_mesh(
        self, water_depth: np.ndarray, base_height: float = 0.0
    ) -> Mesh3D:
        """Generate water surface mesh.

        Args:
            water_depth: 2D array of water depth values
            base_height: Base elevation for zero depth

        Returns:
            Water surface mesh
        """
        # Generate grid coordinates
        x_coords = np.linspace(self.bounds.min_x, self.bounds.max_x, self.width)
        y_coords = np.linspace(self.bounds.min_y, self.bounds.max_y, self.height)

        xx, yy = np.meshgrid(x_coords, y_coords)

        # Resample water depth to match grid
        if water_depth.shape != (self.height, self.width):
            water_depth = self._resample_depth(water_depth, self.height, self.width)

        # Calculate water surface height
        water_height = base_height + water_depth

        # Create vertices
        vertices = np.column_stack(
            [xx.flatten(), yy.flatten(), water_height.flatten()]
        ).astype(np.float32)

        # Generate faces
        faces = self._generate_grid_faces(self.height, self.width)

        # Generate UVs
        uvs = self._generate_uvs(self.height, self.width)

        # Create mesh
        mesh = Mesh3D(vertices=vertices, faces=faces, uvs=uvs)
        mesh.normals = mesh.calculate_normals()

        mesh.metadata = {
            "type": "water_surface",
            "bounds": self.bounds.to_dict(),
            "resolution": self.resolution,
            "max_depth": float(np.max(water_depth)),
            "avg_depth": float(np.mean(water_depth)),
        }

        return mesh

    def _resample_depth(self, depth: np.ndarray, height: int, width: int) -> np.ndarray:
        """Resample water depth to target dimensions.

        Args:
            depth: Source depth array
            height: Target height
            width: Target width

        Returns:
            Resampled depth array
        """
        from scipy.ndimage import zoom

        zoom_y = height / depth.shape[0]
        zoom_x = width / depth.shape[1]

        return zoom(depth, (zoom_y, zoom_x), order=1, mode="nearest")

    def _generate_grid_faces(self, height: int, width: int) -> np.ndarray:
        """Generate triangle faces for grid."""
        faces = []

        for row in range(height - 1):
            for col in range(width - 1):
                i0 = row * width + col
                i1 = i0 + 1
                i2 = (row + 1) * width + col
                i3 = i2 + 1

                faces.append([i0, i2, i1])
                faces.append([i1, i2, i3])

        return np.array(faces, dtype=np.uint32)

    def _generate_uvs(self, height: int, width: int) -> np.ndarray:
        """Generate UV texture coordinates."""
        u = np.linspace(0, 1, width)
        v = np.linspace(0, 1, height)

        uu, vv = np.meshgrid(u, v)

        return np.column_stack([uu.flatten(), vv.flatten()]).astype(np.float32)


class LODMeshGenerator:
    """Level-of-Detail mesh generator for performance optimization.

    Creates multiple detail levels for efficient rendering at different distances.
    """

    def __init__(self, dtm: DigitalTerrainModel):
        """Initialize LOD generator.

        Args:
            dtm: Source digital terrain model
        """
        self.dtm = dtm
        self.base_generator = TerrainMeshGenerator()

    def generate_lod_levels(self, levels: int = 4) -> List[Mesh3D]:
        """Generate multiple LOD levels.

        Args:
            levels: Number of LOD levels (0 = full detail)

        Returns:
            List of meshes from highest to lowest detail
        """
        meshes = []

        for level in range(levels):
            simplification = 1.0 / (2**level)

            logger.info(
                f"Generating LOD level {level}: {simplification * 100:.1f}% detail"
            )

            mesh = self.base_generator.generate_from_dtm(
                self.dtm, simplification=simplification if level > 0 else None
            )

            mesh.metadata["lod_level"] = level
            mesh.metadata["simplification"] = simplification

            meshes.append(mesh)

        return meshes


# Convenience functions
def generate_terrain_mesh(
    dtm: DigitalTerrainModel,
    simplification: Optional[float] = None,
    z_scale: float = 1.0,
) -> Mesh3D:
    """Generate terrain mesh from DTM (convenience function).

    Args:
        dtm: Digital terrain model
        simplification: Optional simplification factor
        z_scale: Vertical exaggeration

    Returns:
        3D terrain mesh
    """
    generator = TerrainMeshGenerator(z_scale=z_scale)
    return generator.generate_from_dtm(dtm, simplification=simplification)


def generate_water_mesh(
    bounds: BoundingBox, water_depth: np.ndarray, resolution: float = 10.0
) -> Mesh3D:
    """Generate water surface mesh (convenience function).

    Args:
        bounds: Spatial bounds
        water_depth: Water depth array
        resolution: Grid resolution

    Returns:
        Water surface mesh
    """
    generator = WaterSurfaceMeshGenerator(bounds, resolution)
    return generator.generate_mesh(water_depth)
