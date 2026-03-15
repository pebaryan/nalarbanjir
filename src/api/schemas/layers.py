"""Pydantic v2 schemas for layer management endpoints."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

LayerType = Literal["dem", "flood_depth", "flood_risk", "vector", "rain", "channel"]


class LayerStyle(BaseModel):
    color:     str            = Field("#38bdf8", description="Hex colour for vector / solid fills")
    colormap:  str            = Field("terrain",  description="Colormap name for raster layers")
    range_min: Optional[float] = Field(None, description="Colormap domain min; None = auto-scale")
    range_max: Optional[float] = Field(None, description="Colormap domain max; None = auto-scale")
    line_width: float          = Field(1.5, ge=0.1, le=20.0)
    point_size: float          = Field(4.0, ge=1.0)


class LayerMetadata(BaseModel):
    crs_epsg:        Optional[int]         = None
    bounds:          Optional[dict]        = None   # {min_x, min_y, max_x, max_y}
    resolution:      Optional[list]        = None   # [x_res, y_res]
    feature_count:   Optional[int]         = None
    source_filename: Optional[str]         = None


# ── Requests ──────────────────────────────────────────────────────────────────

class LayerCreate(BaseModel):
    name:       str        = Field(..., min_length=1, max_length=128)
    type:       LayerType
    data_ref:   str        = Field(..., description="file_id or 'sim:flood_depth' / 'sim:flood_risk'")
    visibility: bool       = True
    opacity:    float      = Field(1.0, ge=0.0, le=1.0)
    z_index:    int        = Field(0,   ge=0)
    style:      LayerStyle    = Field(default_factory=LayerStyle)
    metadata:   LayerMetadata = Field(default_factory=LayerMetadata)


class LayerUpdate(BaseModel):
    name:       Optional[str]         = None
    visibility: Optional[bool]        = None
    opacity:    Optional[float]       = Field(None, ge=0.0, le=1.0)
    z_index:    Optional[int]         = Field(None, ge=0)
    style:      Optional[LayerStyle]  = None


class LayerReorderRequest(BaseModel):
    ordered_ids: list[str] = Field(..., description="All layer IDs ordered bottom→top (index 0 = bottom)")


# ── Response ──────────────────────────────────────────────────────────────────

class LayerResponse(BaseModel):
    id:         str
    name:       str
    type:       LayerType
    visibility: bool
    opacity:    float
    z_index:    int
    style:      LayerStyle
    data_ref:   str
    metadata:   LayerMetadata


class LayerListResponse(BaseModel):
    layers: list[LayerResponse]
    count:  int
