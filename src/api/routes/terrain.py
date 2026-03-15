"""
Terrain information endpoints.

GET /api/terrain/info   — metadata (grid size, cell size, elevation range)
GET /api/terrain/mesh   — simplified elevation grid for Three.js
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.schemas.terrain import TerrainMetadata, BoundingBox

router = APIRouter(tags=["terrain"])


@router.get("/info")
async def terrain_info(request: Request) -> dict:
    """Return terrain configuration and elevation statistics."""
    cfg = request.app.state.config
    sc = cfg.physics.solver_2d

    # If an engine is running use its terrain; otherwise return synthetic info
    engine = getattr(request.app.state, "engine", None)
    if engine is not None and engine._solver_2d is not None and engine._solver_2d._z is not None:
        z = engine._solver_2d._z
        min_elev = float(z.min())
        max_elev = float(z.max())
        source = "solver"
    else:
        min_elev = -cfg.terrain.amplitude
        max_elev = cfg.terrain.amplitude
        source = "synthetic"

    metadata = TerrainMetadata(
        nx=sc.nx,
        ny=sc.ny,
        dx=sc.dx,
        dy=sc.dy,
        bounding_box=BoundingBox(
            min_x=0.0,
            min_y=0.0,
            max_x=sc.nx * sc.dx,
            max_y=sc.ny * sc.dy,
            crs="local",
        ),
        crs="local",
        min_elevation=min_elev,
        max_elevation=max_elev,
        source=source,
    )
    return metadata.model_dump()


@router.get("/mesh")
async def terrain_mesh(request: Request) -> dict:
    """
    Return a coarse (every 10th cell) elevation grid for the Three.js viewport.

    Response is a dict with 'nx', 'ny', 'dx', 'dy', 'elevation' (flat list).
    """
    cfg = request.app.state.config
    sc = cfg.physics.solver_2d

    engine = getattr(request.app.state, "engine", None)
    if engine is not None and engine._solver_2d is not None and engine._solver_2d._z is not None:
        z_full = engine._solver_2d._z
    else:
        # Synthesize on-the-fly
        import numpy as np
        x = np.arange(sc.nx) * sc.dx
        y = np.arange(sc.ny) * sc.dy
        xx, yy = np.meshgrid(x, y, indexing="ij")
        A, L = cfg.terrain.amplitude, cfg.terrain.wavelength
        z_full = A * (np.sin(2 * 3.14159 * xx / L) + np.cos(2 * 3.14159 * yy / L))

    # Downsample by factor 10 for fast transfer
    stride = max(1, min(sc.nx, sc.ny) // 50)
    z_coarse = z_full[::stride, ::stride]
    nx_c, ny_c = z_coarse.shape

    return {
        "nx": nx_c,
        "ny": ny_c,
        "dx": sc.dx * stride,
        "dy": sc.dy * stride,
        "elevation": z_coarse.tolist(),
    }
