"""Create a test GeoTIFF file for upload testing."""

import numpy as np
import rasterio
from rasterio.transform import from_origin
import os

# Create test elevation data
# A simple hill/valley terrain
x = np.linspace(0, 1000, 100)
y = np.linspace(0, 1000, 100)
X, Y = np.meshgrid(x, y)

# Create a hill in the center
elevation = 50 * np.exp(-((X - 500) ** 2 + (Y - 500) ** 2) / 50000)
elevation = elevation.astype(np.float32)

# Define transform
transform = from_origin(0, 1000, 10, 10)

# Create output directory if needed
os.makedirs("data/test", exist_ok=True)

# Write GeoTIFF
output_path = "data/test/test_terrain.tif"
with rasterio.open(
    output_path,
    "w",
    driver="GTiff",
    height=elevation.shape[0],
    width=elevation.shape[1],
    count=1,
    dtype=elevation.dtype,
    crs="EPSG:4326",
    transform=transform,
) as dst:
    dst.write(elevation, 1)
    dst.update_tags(description="Test terrain for flood simulation")

print(f"Created test GeoTIFF: {output_path}")
print(f"Elevation range: {elevation.min():.2f}m to {elevation.max():.2f}m")
print(f"Grid size: {elevation.shape[0]}x{elevation.shape[1]}")
