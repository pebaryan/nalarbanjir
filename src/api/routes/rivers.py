"""
River geometry and parameter API endpoints.

Endpoints:
- POST /api/rivers                          — create new river
- GET  /api/rivers                          — list all rivers
- GET  /api/rivers/{river_id}               — get specific river
- POST /api/rivers/{river_id}/export        — export as GeoJSON
- GET  /api/rivers/{river_id}/mesh          — generate mesh for solver
- DELETE /api/rivers/{river_id}             — delete river
"""

from __future__ import annotations

import logging
import json

from fastapi import APIRouter, Depends, Request, HTTPException

from src.api.schemas.rivers import (
    RiverRequest,
    RiverResponse,
    RiverListResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rivers"])


# ── Helper Functions ────────────────────────────────────────────────────────

def get_rivers(request: Request) -> dict:
    """Get rivers storage from app state."""
    return request.app.state.rivers


def get_rivers_list(request: Request) -> List[str]:
    """Get rivers list from app state."""
    return request.app.state.rivers_list


# ── Create River ───────────────────────────────────────────────────────────

@router.post("", response_model=RiverResponse)
async def create_river(request: Request, river: RiverRequest) -> RiverResponse:
    """
    Create a new river entry.

    Stores river geometry and parameters in memory for use in simulations.
    """
    from datetime import datetime

    rivers = get_rivers(request)
    rivers_list = get_rivers_list(request)

    # Generate unique ID
    river_id = f"river_{len(rivers) + 1}"

    # Store river data
    river_data = {
        "id": river_id,
        "name": river.name,
        "description": river.description,
        "geometry": river.geometry.model_dump(),
        "hydraulic_params": river.hydraulic_params.model_dump(),
        "simulation_settings": river.simulation_settings.model_dump(),
        "metadata": river.metadata.model_dump(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    rivers[river_id] = river_data
    rivers_list.append(river_id)

    logger.info(
        "River created: id=%s name=%s type=%s",
        river_id, river.name, river.geometry.type
    )

    return RiverResponse(
        ok=True,
        river_id=river_id,
        message=f"River '{river.name}' created successfully"
    )


# ── List Rivers ────────────────────────────────────────────────────────────

@router.get("", response_model=RiverListResponse)
async def list_rivers(request: Request) -> RiverListResponse:
    """
    List all rivers.

    Returns all rivers in the storage with their basic information.
    """
    rivers = get_rivers(request)
    rivers_list = get_rivers_list(request)

    rivers_data = [
        rivers[rid] for rid in rivers_list
    ]

    logger.info("Listed %d rivers", len(rivers_data))

    return RiverListResponse(
        rivers=rivers_data,
        count=len(rivers_data)
    )


# ── Get Specific River ─────────────────────────────────────────────────────

@router.get("/{river_id}")
async def get_river(request: Request, river_id: str) -> dict:
    """
    Get specific river details.

    Returns complete river data including geometry, hydraulic parameters,
    and simulation settings.
    """
    rivers = get_rivers(request)

    if river_id not in rivers:
        raise HTTPException(
            status_code=404,
            detail=f"River '{river_id}' not found"
        )

    return rivers[river_id]


# ── Export River as GeoJSON ───────────────────────────────────────────────

@router.get("/{river_id}/export")
async def export_river(request: Request, river_id: str) -> dict:
    """
    Export river data as GeoJSON.

    Creates a GeoJSON Feature with all river data attached as properties.
    """
    rivers = get_rivers(request)

    if river_id not in rivers:
        raise HTTPException(
            status_code=404,
            detail=f"River '{river_id}' not found"
        )

    river = rivers[river_id]

    # Create GeoJSON with all data
    geojson = {
        "type": "Feature",
        "properties": {
            "name": river["name"],
            "description": river["description"],
            "hydraulic_params": river["hydraulic_params"],
            "simulation_settings": river["simulation_settings"],
            "metadata": river["metadata"]
        },
        "geometry": river["geometry"]
    }

    logger.info("Exported river '%s' as GeoJSON", river["name"])

    return {
        "ok": True,
        "format": "geojson",
        "data": geojson,
        "river_id": river_id,
        "message": f"River '{river['name']}' exported successfully"
    }


# ── Generate Mesh for Solver ───────────────────────────────────────────────

@router.get("/{river_id}/mesh")
async def get_river_mesh(request: Request, river_id: str) -> dict:
    """
    Generate mesh from river geometry for solver.

    Creates a simplified mesh representation that can be used with the
    physics solver. For production, integrate with actual mesh generator.
    """
    rivers = get_rivers(request)

    if river_id not in rivers:
        raise HTTPException(
            status_code=404,
            detail=f"River '{river_id}' not found"
        )

    river = rivers[river_id]

    # Extract geometry and generate simplified mesh
    coords = river["geometry"]["coordinates"]
    
    # Handle different geometry types and ensure coordinates are lists
    if river["geometry"]["type"] == "LineString":
        # For LineString, coords is a list of [x, y] pairs
        flat_coords = [list(coord) for linestring in coords for coord in linestring]
    elif river["geometry"]["type"] == "MultiLineString":
        # For MultiLineString, flatten all linestrings
        flat_coords = [list(coord) for linestring in coords for coord in linestring]
    elif river["geometry"]["type"] == "Polygon":
        # For Polygon, use the exterior ring
        flat_coords = [list(coord) for coord in coords[0]]
    else:
        flat_coords = []
    
    # Filter out any invalid coordinate pairs
    flat_coords = [list(coord) for coord in flat_coords if isinstance(coord, list) and len(coord) == 2]
    
    # Generate bounding box for mesh generation
    # This is a simplified approach - production would use proper meshing
    if flat_coords and len(flat_coords) > 0:
        min_x = min(coord[0] for coord in flat_coords)
        max_x = max(coord[0] for coord in flat_coords)
        min_y = min(coord[1] for coord in flat_coords)
        max_y = max(coord[1] for coord in flat_coords)
    else:
        # Default bounds if no valid coordinates
        min_x, max_x = 0, 1000
        min_y, max_y = 0, 1000
    
    # Create mesh parameters
    mesh_data = {
        "type": "river_mesh",
        "river_id": river_id,
        "river_name": river["name"],
        "geometry": river["geometry"],
        "hydraulic_params": params,
        "mesh_bounds": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": max_x - min_x,
            "length": max_y - min_y
        },
        "simulation_settings": river["simulation_settings"],
        "generated_at": __import__('datetime').datetime.now().isoformat()
    }

    logger.info(
        "Generated mesh for river '%s' with bounds: (%.1f, %.1f) to (%.1f, %.1f)",
        river["name"], min_x, min_y, max_x, max_y
    )

    return mesh_data


# ── Delete River ───────────────────────────────────────────────────────────

@router.delete("/{river_id}", response_model=RiverResponse)
async def delete_river(request: Request, river_id: str) -> RiverResponse:
    """
    Delete a river entry.

    Removes the river from storage and cleans up associated data.
    """
    rivers = get_rivers(request)
    rivers_list = get_rivers_list(request)

    if river_id not in rivers:
        raise HTTPException(
            status_code=404,
            detail=f"River '{river_id}' not found"
        )

    # Get river name before deletion
    river_name = rivers[river_id]["name"]

    # Delete from storage
    del rivers[river_id]
    rivers_list.remove(river_id)

    logger.info("Deleted river '%s' (id=%s)", river_name, river_id)

    return RiverResponse(
        ok=True,
        river_id=river_id,
        message=f"River '{river_name}' deleted successfully"
    )