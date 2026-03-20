"""
River geometry and parameter schemas for the flood prediction system.

Provides Pydantic models for:
- River geometry (LineString, Polygon, MultiLineString)
- Hydraulic parameters (width, depth, slope, Manning's n, discharge, velocity)
- Simulation settings (time step, total time, wet/dry threshold)
- Metadata (tags, notes, creator)
"""

from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class RiverGeometry(BaseModel):
    """River geometry definition using GeoJSON-like structure."""
    type: Literal["LineString", "Polygon", "MultiLineString"]
    coordinates: List[List[float]]  # [[[x, y], [x, y]], ...]
    crs: Optional[str] = "local"

    @field_validator('coordinates')
    @classmethod
    def validate_coordinates(cls, v, info):
        """Validate geometry coordinates based on type."""
        geom_type = info.data.get('type', 'LineString')
        
        if geom_type == "LineString" and len(v) < 2:
            raise ValueError("LineString requires at least 2 coordinates")
        if geom_type == "Polygon" and len(v) < 4:
            raise ValueError("Polygon requires at least 4 coordinates")
        if geom_type == "MultiLineString":
            if len(v) < 1:
                raise ValueError("MultiLineString requires at least 1 LineString")
            for i, linestring in enumerate(v):
                if len(linestring) < 2:
                    raise ValueError(f"MultiLineString[{i}] requires at least 2 coordinates")
        return v


class RiverHydraulicParams(BaseModel):
    """Hydraulic parameters for river simulation."""
    width: float = Field(..., gt=0, description="Channel width [m]")
    depth: float = Field(..., gt=0, description="Mean depth [m]")
    slope: float = Field(..., gt=0, description="Slope [m/m]")
    manning_n: float = Field(..., gt=0, description="Manning's n coefficient")
    discharge: float = Field(0.0, ge=0, description="Discharge Q [m³/s]")
    velocity: float = Field(0.0, ge=0, description="Flow velocity [m/s]")


class RiverSimulationSettings(BaseModel):
    """Simulation settings for river-based simulations."""
    time_step: float = Field(..., gt=0, description="Simulation time step [s]")
    total_time: float = Field(..., gt=0, description="Total simulation time [s]")
    wet_dry_threshold: float = Field(0.001, gt=0, description="Wet/dry threshold [m]")


class RiverMetadata(BaseModel):
    """Metadata for river entries."""
    created_by: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags are unique and non-empty."""
        if len(v) != len(set(v)):
            raise ValueError("Tags must be unique")
        return v


class RiverRequest(BaseModel):
    """Complete river data model for creation."""
    name: str = Field(..., min_length=1, max_length=100, description="River name")
    description: Optional[str] = None
    geometry: RiverGeometry
    hydraulic_params: RiverHydraulicParams
    simulation_settings: RiverSimulationSettings
    metadata: RiverMetadata = Field(default_factory=RiverMetadata)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate river name."""
        if not v.strip():
            raise ValueError("River name cannot be empty")
        return v.strip()


class RiverResponse(BaseModel):
    """Response model for river operations."""
    ok: bool
    river_id: str
    message: str


class RiverListResponse(BaseModel):
    """Response model for listing rivers."""
    rivers: List[dict]
    count: int