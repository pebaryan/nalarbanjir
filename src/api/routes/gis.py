"""
GIS / DEM upload and mesh-generation endpoints.

POST /api/gis/upload                         — upload GeoTIFF / ASCII Grid / Shapefile / GeoJSON
GET  /api/gis/files                          — list uploaded files
POST /api/gis/generate_terrain_mesh          — generate Three.js mesh from a DTM
GET  /api/gis/mesh/{mesh_id}                 — retrieve a generated mesh
POST /api/gis/tile-dtm                       — tile a large DTM synchronously
POST /api/gis/tile-async                     — start async tiling (returns task_id)
GET  /api/gis/tiling-progress/{task_id}      — poll async tiling progress
POST /api/gis/tiling-cancel/{task_id}        — cancel an async tiling task
GET  /api/gis/tile/{tile_id}                 — get a single tile mesh
POST /api/gis/visible-tiles                  — get tiles visible from camera position

State stored on app.state:
  gis_storage    : dict[file_id, {type, data, filename}]
  mesh_storage   : dict[mesh_id, {type, data, source_file, params}]
  tiled_dtms     : dict[file_id, list[tile_id]]
  tiling_tasks   : dict[task_id, progress_dict]
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["gis"])

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "nalarbanjir_uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)

# Pixel threshold above which we issue a proxy mesh + async tiles
_LARGE_DTM_PIXELS = 500_000


# ── helpers ───────────────────────────────────────────────────────────────────

def _looks_like_citygml(path: Path) -> bool:
    """Quick check: is the file CityGML by peeking at the first 2 KB?"""
    try:
        chunk = path.read_bytes()[:2048].decode("utf-8", errors="ignore")
        return "citygml" in chunk.lower() or "CityModel" in chunk
    except Exception:
        return False

def _gis(request: Request) -> dict:
    return request.app.state.gis_storage


def _meshes(request: Request) -> dict:
    return request.app.state.mesh_storage


def _tasks(request: Request) -> dict:
    return request.app.state.tiling_tasks


def _tiled(request: Request) -> dict:
    return request.app.state.tiled_dtms


def _tile_mgr(request: Request):
    return request.app.state.tile_manager


# ── upload ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_gis_file(
    request: Request,
    file: UploadFile = File(...),
    target_crs: Optional[int] = Form(None),
) -> JSONResponse:
    """Upload and process a GIS file (GeoTIFF, ASCII Grid, Shapefile, GeoJSON)."""
    try:
        from src.gis.importer import GISImporter, GISImportError

        file_id  = str(uuid.uuid4())
        file_ext = Path(file.filename).suffix.lower()
        temp_path = _UPLOAD_DIR / f"{file_id}{file_ext}"

        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        importer = GISImporter()

        if file_ext in (".tif", ".tiff", ".asc"):
            dtm = importer.import_raster(filepath=temp_path, target_crs=target_crs)

            result = {
                "file_id": file_id,
                "filename": file.filename,
                "type": "raster",
                "format": file_ext,
                "bounds": {
                    "min_x": dtm.bounds.min_x,
                    "min_y": dtm.bounds.min_y,
                    "max_x": dtm.bounds.max_x,
                    "max_y": dtm.bounds.max_y,
                },
                "crs": dtm.crs.epsg_code if hasattr(dtm.crs, "epsg_code") else dtm.crs,
                "resolution": dtm.resolution,
                "dimensions": {"width": dtm.width, "height": dtm.height},
                "elevation_stats": {
                    "min":  float(dtm.elevation_data.min()),
                    "max":  float(dtm.elevation_data.max()),
                    "mean": float(dtm.elevation_data.mean()),
                    "std":  float(dtm.elevation_data.std()),
                },
            }
            _gis(request)[file_id] = {"type": "dtm", "data": dtm, "filename": file.filename}

        elif file_ext in (".gml", ".citygml", ".xml") and _looks_like_citygml(temp_path):
            from src.gis.citygml_parser import parse_citygml

            gdf    = parse_citygml(temp_path, target_crs=target_crs)
            tb     = gdf.total_bounds
            crs_ep = gdf.crs.to_epsg() if gdf.crs else None

            result = {
                "file_id":        file_id,
                "filename":        file.filename,
                "type":            "building",
                "format":          "citygml",
                "feature_count":   len(gdf),
                "crs":             crs_ep,
                "bounds": {
                    "min_x": float(tb[0]), "min_y": float(tb[1]),
                    "max_x": float(tb[2]), "max_y": float(tb[3]),
                },
                "height_range": {
                    "min": float(gdf["height"].min()) if "height" in gdf.columns else 0.0,
                    "max": float(gdf["height"].max()) if "height" in gdf.columns else 20.0,
                },
            }
            _gis(request)[file_id] = {"type": "building", "data": gdf, "filename": file.filename}

        elif file_ext in (".shp", ".geojson", ".json", ".gpkg", ".zip"):
            # ZIP archives may contain a complete Shapefile set
            load_path = f"zip://{temp_path}" if file_ext == ".zip" else temp_path
            vector_data = importer.import_vector(filepath=load_path, target_crs=target_crs)

            bounds = None
            if hasattr(vector_data, "geodataframe"):
                tb = vector_data.geodataframe.total_bounds  # [minx, miny, maxx, maxy]
                bounds = {"min_x": float(tb[0]), "min_y": float(tb[1]),
                          "max_x": float(tb[2]), "max_y": float(tb[3])}

            result = {
                "file_id":       file_id,
                "filename":      file.filename,
                "type":          "vector",
                "format":        file_ext,
                "feature_count": vector_data.feature_count,
                "crs": vector_data.crs if isinstance(vector_data.crs, int)
                       else getattr(vector_data.crs, "epsg_code", None),
                "geometry_types": vector_data.geometry_types,
                "bounds":         bounds,
                "attributes": list(vector_data.geodataframe.columns)[:10]
                              if hasattr(vector_data, "geodataframe") else [],
            }
            _gis(request)[file_id] = {"type": "vector", "data": vector_data, "filename": file.filename}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")

        logger.info("Uploaded %s → %s", file.filename, file_id)
        return JSONResponse(content=result)

    except GISImportError as exc:
        logger.error("GIS import error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── list files ────────────────────────────────────────────────────────────────

@router.get("/files")
async def list_uploaded_files(request: Request) -> JSONResponse:
    files = []
    for file_id, data in _gis(request).items():
        info: dict = {"file_id": file_id, "filename": data.get("filename", "unknown"), "type": data.get("type")}
        if data["type"] == "dtm":
            dtm = data["data"]
            info["dimensions"] = {"width": dtm.width, "height": dtm.height}
            info["total_pixels"] = dtm.width * dtm.height
            info["bounds"] = {
                "min_x": dtm.bounds.min_x, "min_y": dtm.bounds.min_y,
                "max_x": dtm.bounds.max_x, "max_y": dtm.bounds.max_y,
            }
        files.append(info)
    return JSONResponse(content={"files": files, "count": len(files)})


# ── generate terrain mesh ─────────────────────────────────────────────────────

@router.post("/generate_terrain_mesh")
async def generate_terrain_mesh_endpoint(request: Request, params: dict) -> JSONResponse:
    """Generate a Three.js terrain mesh from an uploaded DTM."""
    try:
        from src.gis.mesh_generator import generate_terrain_mesh

        file_id = params.get("file_id")
        gis = _gis(request)
        if not file_id or file_id not in gis:
            raise HTTPException(status_code=400, detail="Invalid or missing file_id")

        stored = gis[file_id]
        if stored["type"] != "dtm":
            raise HTTPException(status_code=400, detail="File is not a raster DTM")

        dtm          = stored["data"]
        total_pixels = dtm.width * dtm.height
        meshes       = _meshes(request)
        tasks        = _tasks(request)

        if total_pixels > _LARGE_DTM_PIXELS:
            # Quick proxy mesh (1% resolution) + background async tiling
            proxy_mesh    = generate_terrain_mesh(dtm=dtm, simplification=0.01, z_scale=1.0)
            proxy_mesh_id = str(uuid.uuid4())
            meshes[proxy_mesh_id] = {"type": "terrain", "data": proxy_mesh,
                                     "source_file": file_id, "params": {**params, "is_proxy": True}}

            task_id          = str(uuid.uuid4())
            estimated_tiles  = max(1, total_pixels // 40_000)
            tasks[task_id]   = {
                "file_id":         file_id,
                "status":          "starting",
                "progress":        0,
                "total_tiles":     estimated_tiles,
                "completed_tiles": 0,
                "message":         "Initializing tiling process...",
                "tile_ids":        [],
                "started_at":      time.time(),
            }

            def _do_tiling():
                try:
                    tasks[task_id]["status"]  = "processing"
                    tasks[task_id]["message"] = "Creating tiles..."
                    tile_ids = _tile_mgr(request).create_tiles_from_dtm(dtm)
                    _tiled(request)[file_id]  = tile_ids
                    tasks[task_id].update({
                        "status":          "completed",
                        "progress":        100,
                        "completed_tiles": len(tile_ids),
                        "total_tiles":     len(tile_ids),
                        "tile_ids":        tile_ids,
                        "message":         f"Tiling complete! Created {len(tile_ids)} tiles",
                        "completed_at":    time.time(),
                    })
                except Exception as exc:
                    logger.error("Async tiling error: %s", exc)
                    tasks[task_id].update({"status": "error", "message": str(exc)})

            t = threading.Thread(target=_do_tiling, daemon=True)
            t.start()

            return JSONResponse(content={
                "status":          "proxy",
                "file_id":         file_id,
                "proxy_mesh_id":   proxy_mesh_id,
                "task_id":         task_id,
                "total_pixels":    total_pixels,
                "estimated_tiles": estimated_tiles,
                "message":         f"Proxy mesh ready. Detailed tiling in progress ({estimated_tiles} tiles estimated).",
                "use_proxy":       True,
                "bounds": {
                    "min_x": float(dtm.bounds.min_x), "min_y": float(dtm.bounds.min_y),
                    "max_x": float(dtm.bounds.max_x), "max_y": float(dtm.bounds.max_y),
                },
            })

        simplification = params.get("simplification", 0.5)
        z_scale        = params.get("z_scale", 1.0)
        mesh           = generate_terrain_mesh(dtm=dtm, simplification=simplification, z_scale=z_scale)
        mesh_id        = str(uuid.uuid4())
        meshes[mesh_id] = {"type": "terrain", "data": mesh, "source_file": file_id, "params": params}

        return JSONResponse(content={
            "mesh_id": mesh_id,
            "type":    "terrain",
            "file_id": file_id,
            "metadata": {
                "vertex_count":    len(mesh.vertices) if mesh.vertices is not None else 0,
                "face_count":      len(mesh.faces)    if mesh.faces    is not None else 0,
                "bounds": {
                    "min_x": float(dtm.bounds.min_x), "min_y": float(dtm.bounds.min_y),
                    "max_x": float(dtm.bounds.max_x), "max_y": float(dtm.bounds.max_y),
                },
                "simplification": simplification,
                "z_scale":        z_scale,
            },
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Mesh generation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── get mesh ──────────────────────────────────────────────────────────────────

@router.get("/mesh/{mesh_id}")
async def get_mesh_data(mesh_id: str, request: Request) -> JSONResponse:
    meshes = _meshes(request)
    if mesh_id not in meshes:
        raise HTTPException(status_code=404, detail=f"Mesh not found: {mesh_id}")

    info      = meshes[mesh_id]
    mesh_data = info["data"]
    return JSONResponse(content={
        "mesh_id":          mesh_id,
        "type":             info["type"],
        "threejs_geometry": mesh_data.to_threejs_buffergeometry(),
        "metadata": {
            "vertex_count":      len(mesh_data.vertices) if mesh_data.vertices is not None else 0,
            "face_count":        len(mesh_data.faces)    if mesh_data.faces    is not None else 0,
            "has_normals":       mesh_data.normals        is not None,
            "has_uvs":           mesh_data.uvs            is not None,
            "has_vertex_colors": mesh_data.colors         is not None,
        },
    })


# ── tile DTM (sync) ───────────────────────────────────────────────────────────

@router.post("/tile-dtm")
async def tile_dtm_endpoint(request: Request, params: dict) -> JSONResponse:
    try:
        file_id = params.get("file_id")
        gis     = _gis(request)
        if not file_id or file_id not in gis:
            raise HTTPException(status_code=400, detail="Invalid or missing file_id")

        stored = gis[file_id]
        if stored["type"] != "dtm":
            raise HTTPException(status_code=400, detail="File is not a raster DTM")

        tile_ids               = _tile_mgr(request).create_tiles_from_dtm(stored["data"])
        _tiled(request)[file_id] = tile_ids

        return JSONResponse(content={
            "file_id":    file_id,
            "tile_count": len(tile_ids),
            "tiles":      tile_ids,
            "stats":      _tile_mgr(request).get_stats(),
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Tile creation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── tile DTM (async) ──────────────────────────────────────────────────────────

@router.post("/tile-async")
async def start_async_tiling(request: Request, params: dict) -> JSONResponse:
    try:
        file_id = params.get("file_id")
        gis     = _gis(request)
        if not file_id or file_id not in gis:
            raise HTTPException(status_code=400, detail="Invalid or missing file_id")

        stored = gis[file_id]
        if stored["type"] != "dtm":
            raise HTTPException(status_code=400, detail="File is not a raster DTM")

        dtm             = stored["data"]
        task_id         = str(uuid.uuid4())
        estimated_tiles = max(1, (dtm.width * dtm.height) // 40_000)
        tasks           = _tasks(request)

        tasks[task_id] = {
            "file_id":         file_id,
            "status":          "starting",
            "progress":        0,
            "total_tiles":     estimated_tiles,
            "completed_tiles": 0,
            "message":         "Initializing tiling process...",
            "tile_ids":        [],
            "started_at":      time.time(),
        }

        def _do_tiling():
            try:
                tasks[task_id]["status"]  = "processing"
                tasks[task_id]["message"] = "Creating tiles..."

                def _progress(current, total, message):
                    tasks[task_id].update({
                        "completed_tiles": current,
                        "total_tiles":     total,
                        "progress":        int((current / max(total, 1)) * 100),
                        "message":         message,
                    })

                tile_ids = _tile_mgr(request).create_tiles_from_dtm(dtm, progress_callback=_progress)
                _tiled(request)[file_id] = tile_ids
                tasks[task_id].update({
                    "status":          "completed",
                    "progress":        100,
                    "completed_tiles": len(tile_ids),
                    "total_tiles":     len(tile_ids),
                    "tile_ids":        tile_ids,
                    "message":         f"Tiling complete! Created {len(tile_ids)} tiles",
                    "completed_at":    time.time(),
                })
            except Exception as exc:
                logger.error("Async tiling error: %s", exc)
                tasks[task_id].update({"status": "error", "message": str(exc)})

        threading.Thread(target=_do_tiling, daemon=True).start()

        return JSONResponse(content={
            "task_id":         task_id,
            "status":          "started",
            "estimated_tiles": estimated_tiles,
            "message":         f"Tiling started. Poll /api/gis/tiling-progress/{task_id} for updates.",
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Start async tiling error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── tiling progress / cancel ──────────────────────────────────────────────────

@router.get("/tiling-progress/{task_id}")
async def get_tiling_progress(task_id: str, request: Request) -> JSONResponse:
    tasks = _tasks(request)
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id].copy()
    if "started_at" in task:
        task["elapsed_seconds"] = time.time() - task["started_at"]
    return JSONResponse(content=task)


@router.post("/tiling-cancel/{task_id}")
async def cancel_tiling_task(task_id: str, request: Request) -> JSONResponse:
    tasks = _tasks(request)
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    tasks[task_id].update({
        "status":       "cancelled",
        "message":      "Task cancelled by user",
        "cancelled_at": time.time(),
    })
    return JSONResponse(content={"task_id": task_id, "status": "cancelled"})


# ── get tile ──────────────────────────────────────────────────────────────────

@router.get("/tile/{tile_id}")
async def get_tile_endpoint(tile_id: str, request: Request) -> JSONResponse:
    try:
        from src.gis.tile_manager import LODLevel

        tile = _tile_mgr(request).get_tile_by_id(tile_id)
        if not tile:
            raise HTTPException(status_code=404, detail=f"Tile not found: {tile_id}")

        mesh_data = tile.lod_meshes.get(LODLevel.L0, {})
        attrs     = mesh_data.get("data", {}).get("attributes", {})
        index     = mesh_data.get("data", {}).get("index", {})

        return JSONResponse(content={
            "tile_id": tile_id,
            "bounds": {
                "min_x": tile.bounds.min_x, "min_y": tile.bounds.min_y,
                "max_x": tile.bounds.max_x, "max_y": tile.bounds.max_y,
            },
            "resolution": tile.resolution,
            "vertices":   attrs.get("position", {}).get("array", []),
            "indices":    index.get("array", []),
            "normals":    attrs.get("normal",   {}).get("array", []),
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Get tile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── vector GeoJSON ────────────────────────────────────────────────────────────

@router.get("/vector/{file_id}")
async def get_vector_geojson(file_id: str, request: Request) -> JSONResponse:
    """Return a stored vector dataset as GeoJSON (coordinates in source CRS)."""
    gis = _gis(request)
    if file_id not in gis:
        raise HTTPException(status_code=404, detail="File not found")

    stored = gis[file_id]
    if stored["type"] != "vector":
        raise HTTPException(status_code=400, detail="File is not a vector dataset")

    import json
    vd  = stored["data"]
    gdf = vd.geodataframe

    # total_bounds: [minx, miny, maxx, maxy]
    tb     = gdf.total_bounds
    bounds = {"min_x": float(tb[0]), "min_y": float(tb[1]),
              "max_x": float(tb[2]), "max_y": float(tb[3])}

    crs_epsg = vd.crs if isinstance(vd.crs, int) else getattr(vd.crs, "epsg_code", None)

    return JSONResponse(content={
        "file_id":   file_id,
        "filename":  stored.get("filename", ""),
        "crs_epsg":  crs_epsg,
        "bounds":    bounds,
        "geojson":   json.loads(gdf.to_json()),
    })


# ── elevation grid (for Three.js DEM rendering) ───────────────────────────────

@router.get("/elevation/{file_id}")
async def get_elevation_grid(
    file_id: str,
    request: Request,
    max_size: int = Query(256, ge=16, le=1024, description="Max grid dimension after downsampling"),
) -> JSONResponse:
    """
    Return the elevation grid of an uploaded DTM, downsampled to ≤ max_size×max_size.

    Response format matches /api/terrain/mesh:
      { nx, ny, dx, dy, min_x, min_y, max_x, max_y, elevation: number[][] }

    elevation[i][j] = elevation at scene x = i*dx, z = j*dy  (nx outer, ny inner).
    """
    import numpy as np

    gis = _gis(request)
    if file_id not in gis:
        raise HTTPException(status_code=404, detail="File not found")

    stored = gis[file_id]
    if stored["type"] != "dtm":
        raise HTTPException(status_code=400, detail="File is not a raster DTM")

    dtm = stored["data"]
    elev = dtm.elevation_data  # shape (ny, nx) — standard raster (rows first)

    raw_ny, raw_nx = elev.shape

    # Downsample so the larger dimension ≤ max_size
    stride = max(1, max(raw_nx, raw_ny) // max_size)
    elev_ds = elev[::stride, ::stride]          # still (ny_ds, nx_ds)
    ny_ds, nx_ds = elev_ds.shape

    dx = dtm.resolution[0] * stride
    dy = dtm.resolution[1] * stride

    # Replace nodata with the mean of valid cells
    nodata = dtm.nodata_value
    valid  = elev_ds[elev_ds != nodata]
    fill   = float(valid.mean()) if len(valid) > 0 else 0.0
    elev_clean = np.where(elev_ds == nodata, fill, elev_ds).astype(float)

    # Transpose to (nx_ds, ny_ds) so elevation[i][j] = elev at col i, row j
    elev_t = elev_clean.T  # shape (nx_ds, ny_ds)

    return JSONResponse(content={
        "file_id": file_id,
        "nx":  nx_ds,
        "ny":  ny_ds,
        "dx":  dx,
        "dy":  dy,
        "min_x": float(dtm.bounds.min_x),
        "min_y": float(dtm.bounds.min_y),
        "max_x": float(dtm.bounds.max_x),
        "max_y": float(dtm.bounds.max_y),
        "elevation": elev_t.tolist(),
    })


# ── buildings (CityGML) ───────────────────────────────────────────────────────

@router.get("/buildings/{file_id}")
async def get_buildings_geojson(file_id: str, request: Request) -> JSONResponse:
    """
    Return buildings from a parsed CityGML file as GeoJSON.

    Each feature has a 'height' property (metres) plus any available CityGML
    scalar attributes (function, usage, storeysAboveGround, roofType …).
    """
    gis = _gis(request)
    if file_id not in gis:
        raise HTTPException(status_code=404, detail="File not found")

    stored = gis[file_id]
    if stored["type"] != "building":
        raise HTTPException(status_code=400, detail="File is not a CityGML building dataset")

    import json
    gdf = stored["data"]
    tb  = gdf.total_bounds
    crs_ep = gdf.crs.to_epsg() if gdf.crs else None

    return JSONResponse(content={
        "file_id":       file_id,
        "filename":      stored.get("filename", ""),
        "crs_epsg":      crs_ep,
        "feature_count": len(gdf),
        "bounds": {
            "min_x": float(tb[0]), "min_y": float(tb[1]),
            "max_x": float(tb[2]), "max_y": float(tb[3]),
        },
        "geojson": json.loads(gdf.to_json()),
    })


# ── visible tiles ─────────────────────────────────────────────────────────────

@router.post("/visible-tiles")
async def get_visible_tiles_endpoint(request: Request, params: dict) -> JSONResponse:
    try:
        camera_pos    = params.get("camera_position", [0, 0, 0])
        view_distance = params.get("view_distance", 2000)
        visible       = _tile_mgr(request).get_visible_tiles(
            camera_pos=tuple(camera_pos), view_distance=view_distance
        )
        return JSONResponse(content={
            "visible_tiles":   [t.tile_id for t in visible],
            "count":           len(visible),
            "camera_position": camera_pos,
            "view_distance":   view_distance,
        })
    except Exception as exc:
        logger.error("Get visible tiles error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
