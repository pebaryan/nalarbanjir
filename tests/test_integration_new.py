"""Integration tests for flood prediction system.

Tests the complete workflow from GIS import to simulation results.
"""

import pytest
import numpy as np
import sys
from pathlib import Path
import tempfile
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gis.importer import GISImporter
from gis.mesh_generator import (
    TerrainMeshGenerator,
    WaterSurfaceMeshGenerator,
    generate_terrain_mesh,
    generate_water_mesh,
)
from gis.models import (
    DigitalTerrainModel,
    BoundingBox,
    SpatialReferenceSystem,
)
from physics.weather import WeatherSimulator
from physics.flood_physics_3d import FloodPhysicsEngine3D


class TestGISWorkflow:
    """Test complete GIS import and mesh generation workflow."""

    def test_dtm_import_to_mesh_workflow(self):
        """Test DTM import to mesh generation workflow."""
        # Create a simple DTM
        nx, ny = 50, 50
        elevation = np.random.uniform(0, 100, (nx, ny))

        bounds = BoundingBox(
            min_x=0.0, min_y=0.0, max_x=1000.0, max_y=1000.0, epsg=4326
        )

        dtm = DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=20.0,
            crs=4326,
        )

        # Generate terrain mesh
        mesh = generate_terrain_mesh(dtm, simplification=0.5)

        # Verify mesh
        assert mesh is not None
        assert len(mesh.vertices) > 0
        assert len(mesh.faces) > 0

        # Export to Three.js format
        threejs_data = mesh.to_threejs_buffer_geometry()
        assert "vertices" in threejs_data
        assert "indices" in threejs_data

    def test_water_mesh_generation(self):
        """Test water mesh generation workflow."""
        bounds = BoundingBox(
            min_x=0.0, min_y=0.0, max_x=1000.0, max_y=1000.0, epsg=4326
        )

        # Create water depth array
        water_depth = np.ones((100, 100)) * 2.5

        # Generate water mesh
        mesh = generate_water_mesh(bounds, water_depth, resolution=10.0)

        assert mesh is not None
        assert len(mesh.vertices) > 0
        assert len(mesh.faces) > 0


class TestWeatherFloodIntegration:
    """Test weather and flood simulation integration."""

    def test_rainfall_to_flood_workflow(self):
        """Test rainfall input to flood simulation workflow."""
        # Initialize weather
        weather = WeatherSimulator(grid_size=(50, 50))
        weather.setup_rainfall(
            intensity_mm_hr=50.0,
            duration_hours=2.0,
            distribution="uniform",
        )

        # Get rainfall field
        rainfall_field = weather.get_rainfall_field(time_hours=0.0)

        # Initialize flood simulation
        flood = FloodPhysicsEngine3D(grid_size=(50, 50), dx=20.0)

        # Flat terrain
        elevation = np.zeros((50, 50))
        flood.set_terrain(elevation)

        # Set rainfall as source
        flood.set_rainfall(rainfall_field)

        # Run simulation for 1 hour
        initial_volume = flood.get_total_volume()

        for _ in range(360):  # 1 hour with 10-second steps
            flood.step(dt=10.0)

        final_volume = flood.get_total_volume()

        # Volume should have increased due to rainfall
        assert final_volume > initial_volume

    def test_weather_flood_synchronization(self):
        """Test weather and flood simulation time synchronization."""
        weather = WeatherSimulator(grid_size=(30, 30))
        weather.setup_rainfall(
            intensity_mm_hr=20.0,
            duration_hours=1.0,
            temporal_pattern="peak",
        )

        flood = FloodPhysicsEngine3D(grid_size=(30, 30), dx=10.0)
        flood.set_terrain(np.zeros((30, 30)))

        # Run coupled simulation
        outputs = []
        for hour in range(3):
            # Get weather at current time
            rainfall = weather.get_rainfall_field(time_hours=hour)
            flood.set_rainfall(rainfall)

            # Run flood for 1 hour
            for _ in range(360):
                flood.step(dt=10.0)

            outputs.append(
                {
                    "hour": hour,
                    "rainfall": float(np.mean(rainfall)),
                    "flood_volume": flood.get_total_volume(),
                }
            )

        # Peak rainfall should be in the middle (hour 1)
        assert outputs[1]["rainfall"] > outputs[0]["rainfall"]


class TestEndToEndSimulation:
    """Test complete end-to-end simulation workflows."""

    def test_complete_flood_scenario(self):
        """Test a complete flood scenario from setup to results."""
        # Step 1: Create terrain
        nx, ny = 40, 40
        x = np.linspace(0, 100, nx)
        y = np.linspace(0, 100, ny)
        X, Y = np.meshgrid(x, y)

        # Create valley terrain
        elevation = 50 * np.exp(-((X - 50) ** 2 + (Y - 50) ** 2) / 500)

        # Step 2: Initialize flood simulation
        flood = FloodPhysicsEngine3D(grid_size=(nx, ny), dx=2.5)
        flood.set_terrain(elevation)
        flood.set_boundary_conditions("open")

        # Step 3: Add initial water at high point
        flood.add_initial_water_source(
            x=20, y=20, depth=5.0, radius=3, shape="circular"
        )

        # Step 4: Add rainfall
        weather = WeatherSimulator(grid_size=(nx, ny))
        weather.setup_rainfall(intensity_mm_hr=30.0, duration_hours=0.5)
        rainfall = weather.get_rainfall_field(0.0)
        flood.set_rainfall(rainfall)

        # Step 5: Run simulation
        results = []
        for i in range(100):
            state = flood.step()
            if i % 10 == 0:
                results.append(
                    {
                        "step": i,
                        "time": state.time,
                        "max_depth": flood.get_maximum_depth(),
                        "flood_extent": flood.get_flood_extent(),
                    }
                )

        # Verify results
        assert len(results) == 10
        assert results[-1]["max_depth"] > 0
        assert results[-1]["flood_extent"] > 0

    def test_mesh_export_to_simulation(self):
        """Test mesh export and simulation integration."""
        # Create simple terrain
        nx, ny = 30, 30
        elevation = np.random.uniform(0, 50, (nx, ny))

        bounds = BoundingBox(min_x=0.0, min_y=0.0, max_x=300.0, max_y=300.0, epsg=4326)

        dtm = DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=10.0,
            crs=4326,
        )

        # Generate mesh
        terrain_mesh = generate_terrain_mesh(dtm)
        threejs_data = terrain_mesh.to_threejs_buffer_geometry()

        # Verify mesh can be serialized
        json_str = json.dumps(threejs_data)
        assert len(json_str) > 0

        # Deserialize and use for simulation
        imported_data = json.loads(json_str)
        assert "vertices" in imported_data
        assert "indices" in imported_data

    def test_multi_source_simulation(self):
        """Test simulation with multiple water sources."""
        flood = FloodPhysicsEngine3D(grid_size=(60, 60), dx=10.0)
        flood.set_terrain(np.zeros((60, 60)))

        # Add multiple sources
        sources = [
            {"x": 15, "y": 15, "depth": 3.0, "radius": 4},
            {"x": 30, "y": 30, "depth": 4.0, "radius": 5},
            {"x": 45, "y": 45, "depth": 2.5, "radius": 3},
        ]

        for source in sources:
            flood.add_initial_water_source(**source)

        # Run simulation
        for _ in range(50):
            flood.step()

        # Verify water has spread
        flood_extent = flood.get_flood_extent()
        assert flood_extent > 0

        # Verify velocities are reasonable
        max_velocity = np.max(flood.get_velocity_magnitude())
        assert max_velocity < 10.0  # Should be less than 10 m/s


class TestPerformanceWorkflows:
    """Test performance-critical workflows."""

    def test_large_grid_simulation(self):
        """Test simulation with larger grid."""
        nx, ny = 100, 100

        flood = FloodPhysicsEngine3D(grid_size=(nx, ny), dx=5.0)
        flood.set_terrain(np.random.uniform(0, 20, (nx, ny)))

        # Add source
        flood.add_initial_water_source(x=50, y=50, depth=3.0, radius=10)

        # Run small number of steps
        import time

        start = time.time()

        for _ in range(10):
            flood.step()

        elapsed = time.time() - start

        # Should complete in reasonable time (< 5 seconds for 10 steps)
        assert elapsed < 5.0

    def test_mesh_generation_performance(self):
        """Test mesh generation performance."""
        nx, ny = 200, 200
        elevation = np.random.uniform(0, 100, (nx, ny))

        bounds = BoundingBox(
            min_x=0.0, min_y=0.0, max_x=2000.0, max_y=2000.0, epsg=4326
        )

        dtm = DigitalTerrainModel(
            elevation_data=elevation,
            bounds=bounds,
            resolution=10.0,
            crs=4326,
        )

        import time

        start = time.time()

        mesh = generate_terrain_mesh(dtm, simplification=0.8)

        elapsed = time.time() - start

        # Should complete in reasonable time (< 2 seconds)
        assert elapsed < 2.0
        assert mesh is not None
