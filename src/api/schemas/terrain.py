"""Pydantic v2 schemas for terrain and tile endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: str = Field("EPSG:4326", description="Coordinate reference system")


class TerrainMetadata(BaseModel):
    nx: int = Field(..., gt=0, description="Grid cells in x")
    ny: int = Field(..., gt=0, description="Grid cells in y")
    dx: float = Field(..., gt=0, description="Cell size x [m]")
    dy: float = Field(..., gt=0, description="Cell size y [m]")
    bounding_box: BoundingBox
    crs: str
    min_elevation: float = Field(..., description="Min bed elevation [m]")
    max_elevation: float = Field(..., description="Max bed elevation [m]")
    source: str = Field("synthetic", description="'synthetic' | 'dem_import' | filename")


class TerrainResponse(BaseModel):
    metadata: TerrainMetadata
    elevation: list[list[float]]    # [nx][ny] meters
    land_use: list[list[int]]       # [nx][ny] 0=water,1=urban,2=agri,3=forest,4=wetland,5=open
    manning_n: list[list[float]]    # [nx][ny] Manning roughness


class TileRequest(BaseModel):
    z: int = Field(..., ge=0, le=20, description="Zoom level")
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    lod: int = Field(0, ge=0, le=3, description="LOD: 0=full, 1=1/4, 2=1/16, 3=1/64")


class TerrainMeshVertex(BaseModel):
    """Three.js-compatible BufferGeometry attribute arrays (flat Float32)."""
    positions: list[float]   # [x,y,z, x,y,z, ...] length = n_vertices * 3
    normals: list[float]     # length = n_vertices * 3
    uvs: list[float]         # length = n_vertices * 2
    indices: list[int]       # triangle indices, length = n_triangles * 3
    colors: list[float]      # per-vertex RGBA, length = n_vertices * 4


class TileResponse(BaseModel):
    tile_id: str = Field(..., description="'z/x/y'")
    z: int
    x: int
    y: int
    lod: int
    mesh: TerrainMeshVertex
