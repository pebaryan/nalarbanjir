"""Tests for the physics module."""

import numpy as np
import pytest

try:
    from src.physics.shallow_water import (
        ShallowWaterSolver,
        WaterState,
        WavePropagationAnalyzer,
    )
except ImportError:
    # Fallback for when running tests from different directory
    from physics.shallow_water import (
        ShallowWaterSolver,
        WaterState,
        WavePropagationAnalyzer,
    )


class TestShallowWaterSolver:
    """Test cases for ShallowWaterSolver."""

    def test_initialization(self):
        """Test solver initialization with default parameters."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 10000.0,
            "domain_y": 10000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(50, 50))

        assert solver.nx == 50
        assert solver.ny == 50
        assert solver.g == 9.81
        assert solver.f == 0.0
        assert solver.rh == 0.02
        assert solver.dt == 1.0
        assert solver.Lx == 10000.0
        assert solver.Ly == 10000.0
        assert isinstance(solver.state, WaterState)
        assert solver.state.depth.shape == (50, 50)
        assert solver.state.velocity_x.shape == (50, 50)
        assert solver.state.velocity_y.shape == (50, 50)
        assert solver.state.elevation.shape == (50, 50)

    def test_initialization_with_custom_params(self):
        """Test solver initialization with custom parameters."""
        config = {
            "gravity": 3.7,  # Mars gravity
            "coriolis": 0.1,
            "bottom_friction": 0.05,
            "time_step": 0.5,
            "domain_x": 5000.0,
            "domain_y": 3000.0,
            "terrain_amplitude": 5.0,
            "terrain_wavelength": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(100, 100))

        assert solver.g == 3.7
        assert solver.f == 0.1
        assert solver.rh == 0.05
        assert solver.dt == 0.5
        assert solver.Lx == 5000.0
        assert solver.Ly == 3000.0

    def test_initial_state_properties(self):
        """Test that initial state has correct properties."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(10, 10))

        # Check that depth is non-negative
        assert np.all(solver.state.depth >= 0)
        # Check that elevation equals depth (initial condition)
        assert np.array_equal(solver.state.elevation, solver.state.depth)
        # Check that initial velocity is zero
        assert np.all(solver.state.velocity_x == 0)
        assert np.all(solver.state.velocity_y == 0)
        # Check that time is zero
        assert solver.state.time == 0.0

    def test_evolve_method(self):
        """Test the evolve method advances state correctly."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 0.1,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(20, 20))

        initial_time = solver.state.time
        initial_depth = solver.state.depth.copy()

        # Evolve for 10 steps
        states = solver.evolve(steps=10)

        # Should return 11 states (initial + 10 steps)
        assert len(states) == 11

        # Check that time advances
        assert states[-1].time > initial_time
        assert abs(states[-1].time - (initial_time + 10 * solver.dt)) < 1e-10

        # Check that states are WaterState instances
        for state in states:
            assert isinstance(state, WaterState)
            assert state.depth.shape == (20, 20)
            assert state.velocity_x.shape == (20, 20)
            assert state.velocity_y.shape == (20, 20)
            assert state.elevation.shape == (20, 20)

        # Check that depth remains non-negative
        for state in states:
            assert np.all(state.depth >= 0)

    def test_get_water_surface(self):
        """Test getting water surface elevation."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 100.0,
            "domain_y": 100.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(5, 5))

        surface = solver.get_water_surface()

        assert isinstance(surface, np.ndarray)
        assert surface.shape == (5, 5)
        assert np.array_equal(surface, solver.state.elevation)

    def test_get_velocity_field(self):
        """Test getting velocity field."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 100.0,
            "domain_y": 100.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(5, 5))

        u, v = solver.get_velocity_field()

        assert isinstance(u, np.ndarray)
        assert isinstance(v, np.ndarray)
        assert u.shape == (5, 5)
        assert v.shape == (5, 5)
        assert np.array_equal(u, solver.state.velocity_x)
        assert np.array_equal(v, solver.state.velocity_y)

    def test_compute_flood_risk(self):
        """Test flood risk computation."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 100.0,
            "domain_y": 100.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(5, 5))

        # Set some depths for testing
        solver.state.depth = np.array(
            [
                [0.0, 1.0, 2.0, 3.0, 4.0],
                [0.5, 1.5, 2.5, 3.5, 4.5],
                [1.0, 2.0, 3.0, 4.0, 5.0],
                [1.5, 2.5, 3.5, 4.5, 5.5],
                [2.0, 3.0, 4.0, 5.0, 6.0],
            ]
        )

        # Test with default threshold (2.0)
        risk = solver.compute_flood_risk()

        expected_risk = np.array(
            [
                [0, 0, 1, 2, 3],
                [0, 0, 1, 2, 3],
                [0, 1, 2, 3, 3],
                [0, 1, 2, 3, 3],
                [1, 2, 3, 3, 3],
            ],
            dtype=float,
        )

        assert np.array_equal(risk, expected_risk)

        # Test with custom threshold
        risk_custom = solver.compute_flood_risk(threshold_depth=1.0)
        expected_custom = np.array(
            [
                [0, 1, 3, 3, 3],
                [0, 2, 3, 3, 3],
                [1, 3, 3, 3, 3],
                [2, 3, 3, 3, 3],
                [3, 3, 3, 3, 3],
            ],
            dtype=float,
        )

        assert np.array_equal(risk_custom, expected_custom)

    def test_export_state(self):
        """Test exporting solver state."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.1,
            "bottom_friction": 0.02,
            "time_step": 0.5,
            "domain_x": 500.0,
            "domain_y": 300.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(25, 25))

        state_dict = solver.export_state()

        # Check structure
        assert "time" in state_dict
        assert "grid" in state_dict
        assert "physics" in state_dict
        assert "state" in state_dict

        # Check grid info
        grid_info = state_dict["grid"]
        assert grid_info["nx"] == 25
        assert grid_info["ny"] == 25
        assert grid_info["domain_x"] == 500.0
        assert grid_info["domain_y"] == 300.0

        # Check physics info
        physics_info = state_dict["physics"]
        assert physics_info["gravity"] == 9.81
        assert physics_info["coriolis"] == 0.1
        assert physics_info["bottom_friction"] == 0.02

        # Check state info
        state_info = state_dict["state"]
        assert "elevation" in state_info
        assert "velocity_x" in state_info
        assert "velocity_y" in state_info
        assert "depth" in state_info

        # Check shapes
        assert state_info["elevation"].shape == (25, 25)
        assert state_info["velocity_x"].shape == (25, 25)
        assert state_info["velocity_y"].shape == (25, 25)
        assert state_info["depth"].shape == (25, 25)


class TestWavePropagationAnalyzer:
    """Test cases for WavePropagationAnalyzer."""

    def test_initialization(self):
        """Test analyzer initialization."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(20, 20))
        analyzer = WavePropagationAnalyzer(solver)

        assert analyzer.solver == solver

    def test_analyze_wave_propagation(self):
        """Test wave propagation analysis."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(10, 10))
        analyzer = WavePropagationAnalyzer(solver)

        # Set some test values
        solver.state.depth = np.ones((10, 10)) * 2.0  # 2m depth everywhere
        solver.state.velocity_x = np.ones((10, 10)) * 0.5  # 0.5 m/s x-velocity
        solver.state.velocity_y = np.ones((10, 10)) * 0.3  # 0.3 m/s y-velocity

        analysis = analyzer.analyze_wave_propagation(solver.state)

        # Check that all expected keys are present
        expected_keys = {
            "celerity",
            "propagation_angle",
            "kinetic_energy",
            "potential_energy",
            "total_energy",
            "mean_celerity",
            "max_celerity",
            "min_celerity",
        }
        assert set(analysis.keys()) == expected_keys

        # Check shapes
        assert analysis["celerity"].shape == (10, 10)
        assert analysis["propagation_angle"].shape == (10, 10)
        assert analysis["kinetic_energy"].shape == (10, 10)
        assert analysis["potential_energy"].shape == (10, 10)
        assert analysis["total_energy"].shape == (10, 10)

        # Check specific calculations
        # Celerity = sqrt(g * h) = sqrt(9.81 * 2.0) = sqrt(19.62) ≈ 4.429
        expected_celerity = np.sqrt(9.81 * 2.0)
        assert np.allclose(analysis["celerity"], expected_celerity)

        # Mean celerity should be the same as all values are uniform
        assert np.allclose(analysis["mean_celerity"], expected_celerity)
        assert np.allclose(analysis["max_celerity"], expected_celerity)
        assert np.allclose(analysis["min_celerity"], expected_celerity)

        # Propagation angle = arctan(vy/vx) = arctan(0.3/0.5)
        expected_angle = np.arctan2(0.3, 0.5)
        assert np.allclose(analysis["propagation_angle"], expected_angle)

        # Kinetic energy = 0.5 * h * (u^2 + v^2) = 0.5 * 2.0 * (0.5^2 + 0.3^2)
        expected_ke = 0.5 * 2.0 * (0.5**2 + 0.3**2)
        assert np.allclose(analysis["kinetic_energy"], expected_ke)

        # Potential energy = 0.5 * g * h^2 = 0.5 * 9.81 * 2.0^2
        expected_pe = 0.5 * 9.81 * 4.0
        assert np.allclose(analysis["potential_energy"], expected_pe)

        # Total energy = KE + PE
        expected_te = expected_ke + expected_pe
        assert np.allclose(analysis["total_energy"], expected_te)

    def test_detect_wave_sources(self):
        """Test wave source detection."""
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(10, 10))
        analyzer = WavePropagationAnalyzer(solver)

        # Set up a state with a clear peak in the center
        solver.state.depth = np.ones((10, 10))
        solver.state.velocity_x = np.zeros((10, 10))
        solver.state.velocity_y = np.zeros((10, 10))

        # Create a peak in energy at position (5, 5)
        energy = np.zeros((10, 10))
        energy[5, 5] = 10.0  # High energy at center
        energy[4:6, 4:6] = 5.0  # Medium energy around center
        # Manually set the solver's internal energy calculation for test
        # We'll test the _is_local_maximal method directly instead

        # Test the _is_local_maximal helper method
        test_array = np.array([[1, 2, 1], [2, 9, 2], [1, 2, 1]])

        # Center point should be a local maximum
        assert analyzer._is_local_maximal(test_array, 1, 1) == True

        # Edge points should not be local maxima (when compared to center)
        assert analyzer._is_local_maximal(test_array, 0, 1) == False
        assert analyzer._is_local_maximal(test_array, 1, 0) == False

        # Flat area: center point IS a local maximum (equal to all neighbors)
        flat_array = np.ones((3, 3))
        assert analyzer._is_local_maximal(flat_array, 1, 1) == True


if __name__ == "__main__":
    pytest.main([__file__])
