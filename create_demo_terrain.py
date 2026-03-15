"""
Create a realistic demo valley terrain for flood simulation proof-of-concept.

Usage:
    python create_demo_terrain.py

Output:
    data/demo/valley.tif  — bowl-shaped valley basin (5 km × 5 km, 25 m cells)

Recommended simulation settings after uploading valley.tif:
    Mode     : 2D
    Rainfall : Uniform, 80 mm/hr, 60 min
    Steps    : 500
"""

import os
import numpy as np


def make_valley(nx=200, ny=200, dx=25.0, dy=25.0):
    """
    Returns elevation array (nx, ny) in metres.

    Shape:
      - Ridges ~20 m high around the perimeter
      - Low basin floor 0–3 m in the centre
      - River channel ~3 m deep running N–S through x = centre
      - Minor tributaries entering from east and west sides
    """
    x = np.linspace(-1.0, 1.0, nx)
    y = np.linspace(-1.0, 1.0, ny)
    xx, yy = np.meshgrid(x, y, indexing="ij")

    ridge_h = 20.0   # m
    chan_d  =  4.0   # m — main channel incision
    trib_d  =  2.0   # m — tributary incision

    # Parabolic bowl
    r = np.sqrt(xx**2 + yy**2)
    z = ridge_h * np.clip(r / 0.85, 0.0, 1.0) ** 2

    # Main N–S channel at x = 0
    main_w = 0.05
    z -= chan_d * np.exp(-(xx / main_w) ** 2)

    # East tributary at y = +0.3, flowing from east wall toward channel
    trib_w = 0.04
    e_mask = xx > 0
    z[e_mask] -= trib_d * np.exp(-(yy[e_mask] - 0.3) ** 2 / trib_w ** 2) \
                        * np.clip((1.0 - xx[e_mask] / 0.85), 0.0, 1.0)

    # West tributary at y = -0.2, flowing from west wall toward channel
    w_mask = xx < 0
    z[w_mask] -= trib_d * np.exp(-(yy[w_mask] + 0.2) ** 2 / trib_w ** 2) \
                        * np.clip((1.0 + xx[w_mask] / 0.85), 0.0, 1.0)

    # Gentle random roughness
    rng = np.random.default_rng(42)
    z += 0.4 * rng.standard_normal((nx, ny))

    return np.maximum(z, 0.0).astype(np.float32)


def save_geotiff(z, nx, ny, dx, dy, path):
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError:
        print("rasterio not installed — saving raw .npy instead")
        npy_path = path.replace(".tif", ".npy")
        os.makedirs(os.path.dirname(os.path.abspath(npy_path)), exist_ok=True)
        np.save(npy_path, z)
        return

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    # UTM Zone 48S (EPSG:32748) — representative of West Java / Bandung region
    west  = 788_000.0    # easting  [m]
    north = 9_240_000.0  # northing [m]
    transform = from_origin(west, north, dx, dy)

    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=ny, width=nx,
        count=1,
        dtype=np.float32,
        crs="EPSG:32748",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        # rasterio: row = y-axis, col = x-axis → transpose
        dst.write(z.T, 1)

    print(f"Saved: {path}")
    print(f"  Grid    : {nx} x {ny} cells  ({nx*dx/1000:.1f} km x {ny*dy/1000:.1f} km)")
    print(f"  Cell    : {dx} m x {dy} m")
    print(f"  Elev    : {z.min():.1f} m – {z.max():.1f} m")
    print(f"  CRS     : EPSG:32748 (UTM Zone 48S)")


if __name__ == "__main__":
    NX, NY, DX, DY = 200, 200, 25.0, 25.0
    z = make_valley(NX, NY, DX, DY)
    save_geotiff(z, NX, NY, DX, DY, "data/demo/valley.tif")

    print()
    print("Recommended settings to see flooding:")
    print("  1. Upload  data/demo/valley.tif  as a DEM layer")
    print("  2. Mode    : 2D")
    print("  3. Rainfall: Uniform, 80 mm/hr, 60 min")
    print("  4. Steps   : 500")
    print("  5. Click Initialize, then Run")
    print("  Water will pool in the basin and drain along the river channel.")
