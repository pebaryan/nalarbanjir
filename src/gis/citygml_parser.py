"""
CityGML building parser.

Supports CityGML 1.0 / 2.0 / 3.0.

Extracts Building (and BuildingPart) elements with:
  - Footprint polygon (from LoD0FootPrint, LoD1Solid, or LoD2Solid)
  - Measured height  (bldg:measuredHeight or Z-range of solid)
  - Scalar attributes (function, usage, storeysAboveGround, yearOfConstruction …)

Returns a GeoDataFrame with a 'height' column and Shapely Polygon geometries.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Namespace detection ───────────────────────────────────────────────────────

_BLDG_URIS = [
    "http://www.opengis.net/citygml/building/2.0",
    "http://www.opengis.net/citygml/building/1.0",
    "http://www.opengis.net/citygml/building/3.0",
]
_GML_URIS = [
    "http://www.opengis.net/gml",
    "http://www.opengis.net/gml/3.2",
]


def _detect_ns(root) -> Tuple[str, str]:
    """Return (bldg_uri, gml_uri) from the document's nsmap."""
    all_uris = set((root.nsmap or {}).values())
    bldg = next((u for u in _BLDG_URIS if u in all_uris), _BLDG_URIS[0])
    gml  = next((u for u in _GML_URIS  if u in all_uris), _GML_URIS[0])
    return bldg, gml


# ── Coordinate helpers ────────────────────────────────────────────────────────

def _poslist_to_pts(text: str, dim: int = 3) -> List[Tuple[float, ...]]:
    """Convert a gml:posList string to a list of (x, y[, z]) tuples."""
    nums = [float(v) for v in text.split() if v.strip()]
    return [tuple(nums[i:i + dim]) for i in range(0, len(nums) - dim + 1, dim)]


def _extract_ring_coords(ring_el, gml_ns: str) -> List[Tuple[float, float]]:
    """Return 2-D (x, y) ring coordinates from a gml:LinearRing element."""
    # Try posList
    poslist = ring_el.find(f"{{{gml_ns}}}posList")
    if poslist is not None and poslist.text:
        # Determine dimensionality from srsDimension attribute, default 3
        dim = int(poslist.get("srsDimension", "3"))
        pts = _poslist_to_pts(poslist.text, dim)
        return [(p[0], p[1]) for p in pts]

    # Try individual pos elements
    pos_els = ring_el.findall(f".//{{{gml_ns}}}pos")
    if pos_els:
        coords = []
        for p in pos_els:
            vals = [float(v) for v in (p.text or "").split()]
            if len(vals) >= 2:
                coords.append((vals[0], vals[1]))
        return coords

    # Try old-style gml:coordinates (comma-separated x,y,z space-separated points)
    coords_el = ring_el.find(f"{{{gml_ns}}}coordinates")
    if coords_el is not None and coords_el.text:
        coords = []
        for triplet in coords_el.text.split():
            parts = [float(v) for v in triplet.split(",")]
            if len(parts) >= 2:
                coords.append((parts[0], parts[1]))
        return coords

    return []


def _extract_ring_coords_3d(ring_el, gml_ns: str) -> List[Tuple[float, float, float]]:
    """Same as _extract_ring_coords but preserves Z."""
    poslist = ring_el.find(f"{{{gml_ns}}}posList")
    if poslist is not None and poslist.text:
        dim = int(poslist.get("srsDimension", "3"))
        pts = _poslist_to_pts(poslist.text, dim)
        return [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in pts]

    pos_els = ring_el.findall(f".//{{{gml_ns}}}pos")
    if pos_els:
        coords = []
        for p in pos_els:
            vals = [float(v) for v in (p.text or "").split()]
            if len(vals) >= 3:
                coords.append((vals[0], vals[1], vals[2]))
            elif len(vals) == 2:
                coords.append((vals[0], vals[1], 0.0))
        return coords

    coords_el = ring_el.find(f"{{{gml_ns}}}coordinates")
    if coords_el is not None and coords_el.text:
        coords = []
        for triplet in coords_el.text.split():
            parts = [float(v) for v in triplet.split(",")]
            if len(parts) >= 3:
                coords.append((parts[0], parts[1], parts[2]))
        return coords

    return []


def _first_polygon_coords(container_el, bldg_ns: str, gml_ns: str) -> Optional[List[Tuple[float, float]]]:
    """Find the first Polygon ring inside any element (MultiSurface, Solid, etc.)."""
    for ring in container_el.iter(f"{{{gml_ns}}}LinearRing"):
        coords = _extract_ring_coords(ring, gml_ns)
        if len(coords) >= 3:
            return coords
    return None


def _bottom_polygon_from_solid(solid_el, bldg_ns: str, gml_ns: str) -> Tuple[Optional[List[Tuple[float, float]]], float]:
    """
    From a LoD1Solid, pick the polygon with the lowest Z centroid as the footprint.
    Returns (coords_2d, base_z).
    """
    best_coords: Optional[List[Tuple[float, float]]] = None
    best_z: float = float("inf")

    for ring in solid_el.iter(f"{{{gml_ns}}}LinearRing"):
        coords3d = _extract_ring_coords_3d(ring, gml_ns)
        if len(coords3d) < 3:
            continue
        z_mean = sum(c[2] for c in coords3d) / len(coords3d)
        if z_mean < best_z:
            best_z = z_mean
            best_coords = [(c[0], c[1]) for c in coords3d]

    return best_coords, (best_z if best_z < float("inf") else 0.0)


def _z_range_from_solid(solid_el, gml_ns: str) -> Tuple[float, float]:
    """Return (min_z, max_z) of all coordinates in a solid element."""
    zvals = []
    for ring in solid_el.iter(f"{{{gml_ns}}}LinearRing"):
        for c in _extract_ring_coords_3d(ring, gml_ns):
            zvals.append(c[2])
    if not zvals:
        return 0.0, 10.0
    return min(zvals), max(zvals)


# ── Building extraction ───────────────────────────────────────────────────────

_SCALAR_ATTRS = [
    "measuredHeight", "storeysAboveGround", "storeysBelowGround",
    "yearOfConstruction", "yearOfDemolition", "function", "usage", "class",
    "roofType",
]


def _extract_building(bldg_el, bldg_ns: str, gml_ns: str):
    """
    Extract one building as a dict with 'geometry' (Shapely Polygon) and scalar properties.
    Returns None if no usable footprint is found.
    """
    from shapely.geometry import Polygon

    # ── Height ────────────────────────────────────────────────────────────────
    height: float = 10.0  # default
    mh = bldg_el.find(f"{{{bldg_ns}}}measuredHeight")
    if mh is not None and mh.text:
        try:
            height = float(mh.text)
        except ValueError:
            pass

    # ── Scalar attributes ─────────────────────────────────────────────────────
    props: dict = {"height": height}
    for attr in _SCALAR_ATTRS:
        el = bldg_el.find(f"{{{bldg_ns}}}{attr}")
        if el is not None and el.text:
            props[attr] = el.text.strip()

    # ── Geometry: try LoD0FootPrint → LoD1Solid → LoD2MultiSurface / LoD2Solid
    footprint_coords = None

    lod0fp = bldg_el.find(f".//{{{bldg_ns}}}lod0FootPrint")
    if lod0fp is not None:
        footprint_coords = _first_polygon_coords(lod0fp, bldg_ns, gml_ns)

    if footprint_coords is None:
        lod1solid = bldg_el.find(f".//{{{bldg_ns}}}lod1Solid")
        if lod1solid is not None:
            coords, base_z = _bottom_polygon_from_solid(lod1solid, bldg_ns, gml_ns)
            footprint_coords = coords
            # If measuredHeight not given, compute from Z range
            if mh is None:
                zmin, zmax = _z_range_from_solid(lod1solid, gml_ns)
                height = max(zmax - zmin, 1.0)
                props["height"] = height

    if footprint_coords is None:
        lod2 = (bldg_el.find(f".//{{{bldg_ns}}}lod2Solid")
                or bldg_el.find(f".//{{{bldg_ns}}}lod2MultiSurface"))
        if lod2 is not None:
            footprint_coords = _first_polygon_coords(lod2, bldg_ns, gml_ns)
            if mh is None:
                # Estimate height from Z range
                zmin, zmax = _z_range_from_solid(lod2, gml_ns)
                height = max(zmax - zmin, 1.0)
                props["height"] = height

    if not footprint_coords or len(footprint_coords) < 3:
        return None

    try:
        geom = Polygon(footprint_coords)
        if not geom.is_valid:
            geom = geom.buffer(0)  # attempt repair
        if geom.is_empty:
            return None
    except Exception:
        return None

    props["geometry"] = geom
    return props


# ── Public entry point ────────────────────────────────────────────────────────

def parse_citygml(filepath: Path, target_crs: Optional[int] = None):
    """
    Parse a CityGML file (.gml / .citygml) and return a GeoDataFrame of buildings.

    Each row has:
      geometry       — Shapely Polygon (footprint)
      height         — building height [m]
      + any available scalar attributes

    Args:
        filepath:   Path to the .gml or .citygml file.
        target_crs: If given, reproject to this EPSG code.

    Returns:
        geopandas.GeoDataFrame
    """
    try:
        from lxml import etree
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError(f"Missing dependency: {exc}") from exc

    tree = etree.parse(str(filepath))
    root = tree.getroot()

    bldg_ns, gml_ns = _detect_ns(root)
    logger.debug("CityGML namespaces: bldg=%s  gml=%s", bldg_ns, gml_ns)

    records = []
    bldg_tag = f"{{{bldg_ns}}}Building"

    for bldg_el in root.iter(bldg_tag):
        rec = _extract_building(bldg_el, bldg_ns, gml_ns)
        if rec:
            records.append(rec)

    # Also check BuildingPart
    part_tag = f"{{{bldg_ns}}}BuildingPart"
    for part_el in root.iter(part_tag):
        rec = _extract_building(part_el, bldg_ns, gml_ns)
        if rec:
            records.append(rec)

    if not records:
        raise ValueError(
            "No building geometries found. "
            "The file may use an unsupported LoD or namespace."
        )

    gdf = gpd.GeoDataFrame(records, geometry="geometry")

    # Detect CRS from srsName on the root element or any geometry element
    srs_name = root.get("srsName", "") or ""
    if not srs_name:
        for el in root.iter():
            srs_name = el.get("srsName", "") or ""
            if srs_name:
                break

    if srs_name:
        epsg_match = re.search(r"(?:EPSG::|urn:ogc:def:crs:EPSG::?)(\d+)", srs_name, re.I)
        if epsg_match:
            epsg = int(epsg_match.group(1))
            try:
                gdf = gdf.set_crs(epsg=epsg, allow_override=True)
            except Exception:
                pass

    if target_crs and gdf.crs is not None:
        try:
            gdf = gdf.to_crs(epsg=target_crs)
        except Exception as exc:
            logger.warning("CRS reprojection failed: %s", exc)

    logger.info("Parsed %d buildings from %s", len(gdf), filepath)
    return gdf
