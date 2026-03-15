"""
Layer management endpoints.

POST   /api/layers                   create a layer (auto-fills metadata from gis_storage)
GET    /api/layers                   list all layers sorted by z_index
GET    /api/layers/{layer_id}        get one layer
PATCH  /api/layers/{layer_id}        update layer config
DELETE /api/layers/{layer_id}        remove a layer
POST   /api/layers/reorder           bulk-update z_index from an ordered list of IDs

State lives on app.state.layer_storage  — dict[layer_id, dict]
"""
from __future__ import annotations

import uuid
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.schemas.layers import (
    LayerCreate, LayerUpdate, LayerReorderRequest,
    LayerResponse, LayerListResponse, LayerMetadata,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["layers"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _store(request: Request) -> dict[str, dict]:
    return request.app.state.layer_storage


def _get_or_404(request: Request, layer_id: str) -> dict:
    layer = _store(request).get(layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail=f"Layer not found: {layer_id}")
    return layer


def _auto_metadata(request: Request, data_ref: str) -> dict:
    """Populate LayerMetadata from gis_storage when data_ref is a file_id."""
    gis = getattr(request.app.state, "gis_storage", {})
    stored = gis.get(data_ref)
    if stored is None:
        return {}

    meta: dict[str, Any] = {}
    if stored["type"] == "dtm":
        dtm = stored["data"]
        meta["source_filename"] = stored.get("filename")
        meta["crs_epsg"] = getattr(dtm.crs, "epsg_code", None) if hasattr(dtm, "crs") else None
        if hasattr(dtm, "bounds"):
            b = dtm.bounds
            meta["bounds"] = {"min_x": b.min_x, "min_y": b.min_y, "max_x": b.max_x, "max_y": b.max_y}
        if hasattr(dtm, "resolution"):
            meta["resolution"] = list(dtm.resolution)
    elif stored["type"] == "vector":
        vd = stored["data"]
        meta["source_filename"] = stored.get("filename")
        meta["feature_count"] = getattr(vd, "feature_count", None)
    return meta


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_layer(body: LayerCreate, request: Request) -> LayerResponse:
    layer_id = str(uuid.uuid4())

    # Auto-populate metadata from uploaded GIS file (if data_ref is a file_id)
    extra_meta = _auto_metadata(request, body.data_ref)
    merged_meta = {**body.metadata.model_dump(), **{k: v for k, v in extra_meta.items() if v is not None}}

    # Assign z_index = current max + 1 if caller leaves it at 0 default
    store = _store(request)
    if body.z_index == 0 and store:
        body.z_index = max(v["z_index"] for v in store.values()) + 1

    record = {
        "id":         layer_id,
        "name":       body.name,
        "type":       body.type,
        "visibility": body.visibility,
        "opacity":    body.opacity,
        "z_index":    body.z_index,
        "style":      body.style.model_dump(),
        "data_ref":   body.data_ref,
        "metadata":   merged_meta,
    }
    store[layer_id] = record
    logger.info("Created layer %s (%s) type=%s", layer_id, body.name, body.type)
    return LayerResponse(**record)


@router.get("")
async def list_layers(request: Request) -> LayerListResponse:
    layers = sorted(_store(request).values(), key=lambda l: l["z_index"])
    return LayerListResponse(
        layers=[LayerResponse(**l) for l in layers],
        count=len(layers),
    )


@router.get("/{layer_id}")
async def get_layer(layer_id: str, request: Request) -> LayerResponse:
    return LayerResponse(**_get_or_404(request, layer_id))


@router.patch("/{layer_id}")
async def update_layer(layer_id: str, body: LayerUpdate, request: Request) -> LayerResponse:
    record = _get_or_404(request, layer_id)

    if body.name       is not None: record["name"]       = body.name
    if body.visibility is not None: record["visibility"] = body.visibility
    if body.opacity    is not None: record["opacity"]    = body.opacity
    if body.z_index    is not None: record["z_index"]    = body.z_index
    if body.style      is not None: record["style"]      = body.style.model_dump()

    _store(request)[layer_id] = record
    return LayerResponse(**record)


@router.delete("/{layer_id}")
async def delete_layer(layer_id: str, request: Request) -> dict:
    _get_or_404(request, layer_id)
    del _store(request)[layer_id]
    logger.info("Deleted layer %s", layer_id)
    return {"ok": True}


@router.post("/reorder")
async def reorder_layers(body: LayerReorderRequest, request: Request) -> LayerListResponse:
    store = _store(request)
    for z_index, layer_id in enumerate(body.ordered_ids):
        if layer_id in store:
            store[layer_id]["z_index"] = z_index
    layers = sorted(store.values(), key=lambda l: l["z_index"])
    return LayerListResponse(
        layers=[LayerResponse(**l) for l in layers],
        count=len(layers),
    )
