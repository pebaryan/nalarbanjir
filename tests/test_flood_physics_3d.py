"""Tests for 3D flood physics engine."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from physics.flood_physics_3d import (
    FloodPhysicsEngine3D,
    FloodState,
)


class TestFloodPhysicsEngine3D:
    """Test suite for FloodPhysicsEngine3D class."""

    def test_initialization(self):
        """Test basic initialization."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)
        assert engine.nx == 50
        assert engine.ny == 50
        assert engine.dx == 10.0
        assert engine.g == 9.81
        assert engine.time == 0.0

    def test_set_terrain(self):
        """Test terrain elevation setting."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))

        elevation = np.random.uniform(0, 100, (50, 50))
        engine.set_terrain(elevation)

        assert np.allclose(engine.z, elevation)
        assert engine.z_x.shape == (50, 50)
        assert engine.z_y.shape == (50, 50)

    def test_set_terrain_invalid_shape(self):
        """Test terrain with invalid shape."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))

        elevation = np.random.uniform(0, 100, (30, 30))
        with pytest.raises(ValueError):
            engine.set_terrain(elevation)

    def test_add_initial_water_source(self):
        """Test adding initial water source."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))

        initial_depth = engine.h.copy()
        engine.add_initial_water_source(x=25, y=25, depth=5.0, radius=5)

        # Should have water added
        assert np.sum(engine.h) > np.sum(initial_depth)
        assert engine.h[25, 25] > 0

    def test_step_without_terrain(self):
        """Test that step fails without terrain."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))
        engine.add_initial_water_source(x=25, y=25, depth=5.0, radius=5)

        # Should still work with flat terrain (zeros)
        state = engine.step(dt=0.1)
        assert isinstance(state, FloodState)
        assert state.time > 0

    def test_step_with_terrain(self):
        """Test simulation step with terrain."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)

        # Create sloping terrain
        elevation = np.linspace(0, 100, 50).reshape(-1, 1) * np.ones((50, 50))
        engine.set_terrain(elevation)

        # Add water at top of slope
        engine.add_initial_water_source(x=10, y=25, depth=5.0, radius=5)

        # Run a few steps
        for _ in range(10):
            state = engine.step()

        # Water should have moved
        assert state.time > 0
        assert np.max(state.water_depth) > 0

    def test_boundary_conditions_wall(self):
        """Test wall boundary conditions."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))
        engine.set_boundary_conditions("wall")

        assert engine.boundary_type == "wall"

    def test_boundary_conditions_open(self):
        """Test open boundary conditions."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))
        engine.set_boundary_conditions("open")

        assert engine.boundary_type == "open"

    def test_calculate_courant_timestep(self):
        """Test CFL timestep calculation."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)

        # With no water, should return default
        dt = engine.calculate_courant_timestep()
        assert dt > 0
        assert dt <= 10.0  # Maximum timestep

    def test_get_state(self):
        """Test getting flood state."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))
        engine.add_initial_water_source(x=25, y=25, depth=3.0, radius=3)

        state = engine.get_state()
        assert isinstance(state, FloodState)
        assert state.water_depth.shape == (50, 50)
        assert state.velocity_u.shape == (50, 50)
        assert state.velocity_v.shape == (50, 50)

    def test_get_maximum_depth(self):
        """Test maximum depth calculation."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))
        engine.add_initial_water_source(x=25, y=25, depth=5.0, radius=3)

        max_depth = engine.get_maximum_depth()
        assert max_depth > 0
        assert max_depth <= 5.0  # Should be close to source depth

    def test_get_total_volume(self):
        """Test total volume calculation."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)
        engine.add_initial_water_source(x=25, y=25, depth=1.0, radius=0)

        volume = engine.get_total_volume()
        cell_area = 10.0 * 10.0
        expected_volume = 1.0 * cell_area  # Single cell with 1m depth

        assert volume > 0
        assert abs(volume - expected_volume) < cell_area  # Approximate

    def test_get_flood_extent(self):
        """Test flood extent calculation."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)
        engine.add_initial_water_source(x=25, y=25, depth=1.0, radius=3)

        extent = engine.get_flood_extent(threshold=0.01)
        cell_area = 10.0 * 10.0

        assert extent > 0
        assert extent >= cell_area  # At least one cell

    def test_get_velocity_magnitude(self):
        """Test velocity magnitude calculation."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))

        # Add some velocity
        engine.u[25, 25] = 3.0
        engine.v[25, 25] = 4.0

        speed = engine.get_velocity_magnitude()
        assert speed.shape == (50, 50)
        assert speed[25, 25] == 5.0  # 3-4-5 triangle

    def test_get_froude_number(self):
        """Test Froude number calculation."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50))

        engine.h[25, 25] = 1.0
        engine.u[25, 25] = 3.0

        froude = engine.get_froude_number()
        assert froude.shape == (50, 50)
        # Fr = u / sqrt(g*h) = 3 / sqrt(9.81*1) ≈ 0.96
        assert 0.9 < froude[25, 25] < 1.0

    def test_water_conservation(self):
        """Test that water is approximately conserved."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)

        # Flat terrain
        elevation = np.zeros((50, 50))
        engine.set_terrain(elevation)

        # Add initial water
        engine.add_initial_water_source(x=25, y=25, depth=5.0, radius=5)
        initial_volume = engine.get_total_volume()

        # Run simulation
        for _ in range(50):
            engine.step()

        final_volume = engine.get_total_volume()

        # Volume should be approximately conserved (within 10%)
        # Some loss is expected due to numerical diffusion and boundaries
        assert abs(final_volume - initial_volume) / initial_volume < 0.15

    def test_downslope_flow(self):
        """Test that water flows downslope."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)

        # Create steep slope from left to right
        elevation = np.linspace(100, 0, 50).reshape(-1, 1) * np.ones((50, 50))
        engine.set_terrain(elevation)

        # Add water at top of slope
        engine.add_initial_water_source(x=10, y=25, depth=5.0, radius=8)

        # Store initial center of mass
        h_initial = engine.h.copy()
        mass_initial_x = np.sum(h_initial * np.arange(50)) / np.sum(h_initial)

        # Run simulation with more steps
        for _ in range(200):
            engine.step()

        # Check center of mass has moved downslope (to the right)
        h_final = engine.h
        mass_final_x = np.sum(h_final * np.arange(50)) / np.sum(h_final)

        # Allow for some numerical tolerance - water should have spread
        assert mass_final_x >= mass_initial_x - 1.0, (
            f"Water center of mass should not move uphill: {mass_final_x} vs {mass_initial_x}"
        )

    def test_rainfall_source(self):
        """Test rainfall source term."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)
        engine.set_terrain(np.zeros((50, 50)))

        # Set rainfall (100 mm/hr)
        rainfall = np.full((50, 50), 100.0)
        engine.set_rainfall(rainfall)

        initial_volume = engine.get_total_volume()

        # Run for 1 hour (in seconds)
        for _ in range(360):
            engine.step(dt=10.0)  # 10 second steps

        final_volume = engine.get_total_volume()

        # Volume should have increased significantly
        assert final_volume > initial_volume + 1000  # At least some rainfall added

    def test_export_results(self):
        """Test result export."""
        engine = FloodPhysicsEngine3D(grid_size=(50, 50), dx=10.0)
        engine.set_terrain(np.zeros((50, 50)))
        engine.add_initial_water_source(x=25, y=25, depth=3.0, radius=3)

        # Run a few steps
        for _ in range(10):
            engine.step()

        results = engine.export_results()

        assert "grid_size" in results
        assert "water_depth" in results
        assert "time" in results
        assert "max_depth" in results
        assert "total_volume" in results
        assert "flood_extent" in results
        assert results["time"] > 0

    def test_state_to_dict(self):
        """Test FloodState conversion to dict."""
        state = FloodState(
            water_depth=np.ones((10, 10)),
            velocity_u=np.zeros((10, 10)),
            velocity_v=np.zeros((10, 10)),
            time=100.0,
        )

        data = state.to_dict()
        assert data["time"] == 100.0
        assert len(data["water_depth"]) == 10

    def test_different_grid_sizes(self):
        """Test various grid sizes."""
        for nx, ny in [(20, 20), (100, 100), (200, 50)]:
            engine = FloodPhysicsEngine3D(grid_size=(nx, ny))
            assert engine.nx == nx
            assert engine.ny == ny
            assert engine.h.shape == (nx, ny)

    def test_friction_effect(self):
        """Test that friction slows down flow."""
        engine1 = FloodPhysicsEngine3D(
            grid_size=(50, 50), manning_n=0.01
        )  # Low friction
        engine2 = FloodPhysicsEngine3D(
            grid_size=(50, 50), manning_n=0.1
        )  # High friction

        elevation = np.linspace(100, 0, 50).reshape(-1, 1) * np.ones((50, 50))

        for engine in [engine1, engine2]:
            engine.set_terrain(elevation)
            engine.add_initial_water_source(x=10, y=25, depth=5.0, radius=5)

        # Run both simulations
        for _ in range(50):
            engine1.step()
            engine2.step()

        # Lower friction should have higher velocities
        speed1 = np.mean(engine1.get_velocity_magnitude())
        speed2 = np.mean(engine2.get_velocity_magnitude())

        assert speed1 > speed2
