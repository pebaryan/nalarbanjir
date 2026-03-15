import sys

sys.path.insert(0, "src")

from gis.mesh_generator import generate_terrain_mesh, Mesh3D
from gis.models import DigitalTerrainModel, BoundingBox
import numpy as np

# Create a simple DTM
elevation = np.random.uniform(0, 50, (50, 50)).astype(np.float32)
bounds = BoundingBox(min_x=0.0, min_y=0.0, max_x=500.0, max_y=500.0, epsg=4326)

dtm = DigitalTerrainModel(
    elevation_data=elevation,
    bounds=bounds,
    resolution=10.0,
    crs=4326,
)

print("Generating mesh...")
mesh = generate_terrain_mesh(dtm, simplification=0.5)

print(f"Mesh type: {type(mesh)}")
print(f"Is Mesh3D: {isinstance(mesh, Mesh3D)}")
print(f"Vertices: {len(mesh.vertices)}")
print(f"Faces: {len(mesh.faces)}")

# Store in dict like server does
storage = {"data": mesh}
retrieved = storage["data"]

print(f"Retrieved type: {type(retrieved)}")
print(f"Has method: {hasattr(retrieved, 'to_threejs_buffergeometry')}")

# Try calling the method
try:
    result = retrieved.to_threejs_buffergeometry()
    print("✓ Method call successful!")
    print(f"Keys in result: {list(result.keys())}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback

    traceback.print_exc()
