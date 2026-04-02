"""Tests for input validation in ShallowWaterSolver."""

import pytest
from src.physics.shallow_water import ShallowWaterSolver


class TestInputValidation:
    """Test input validation for ShallowWaterSolver."""

    def test_valid_config(self):
        """Test that valid configuration is accepted."""
        config = {
            "gravity": 9.81,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        # Should not raise
        solver = ShallowWaterSolver(config=config, grid_resolution=(50, 50))
        assert solver.nx == 50
        assert solver.ny == 50

    def test_negative_gravity(self):
        """Test that negative gravity raises ValueError."""
        config = {"gravity": -9.81}
        
        with pytest.raises(ValueError, match="gravity must be positive"):
            ShallowWaterSolver(config=config)

    def test_zero_gravity(self):
        """Test that zero gravity raises ValueError."""
        config = {"gravity": 0}
        
        with pytest.raises(ValueError, match="gravity must be positive"):
            ShallowWaterSolver(config=config)

    def test_negative_time_step(self):
        """Test that negative time step raises ValueError."""
        config = {"time_step": -1.0}
        
        with pytest.raises(ValueError, match="time_step must be positive"):
            ShallowWaterSolver(config=config)

    def test_negative_bottom_friction(self):
        """Test that negative bottom friction raises ValueError."""
        config = {"bottom_friction": -0.02}
        
        with pytest.raises(ValueError, match="bottom_friction must be non-negative"):
            ShallowWaterSolver(config=config)

    def test_zero_bottom_friction_allowed(self):
        """Test that zero bottom friction is allowed."""
        config = {"bottom_friction": 0.0}
        
        # Should not raise
        solver = ShallowWaterSolver(config=config)
        assert solver.rh == 0.0

    def test_negative_domain_x(self):
        """Test that negative domain_x raises ValueError."""
        config = {"domain_x": -1000.0}
        
        with pytest.raises(ValueError, match="domain_x must be positive"):
            ShallowWaterSolver(config=config)

    def test_negative_domain_y(self):
        """Test that negative domain_y raises ValueError."""
        config = {"domain_y": -1000.0}
        
        with pytest.raises(ValueError, match="domain_y must be positive"):
            ShallowWaterSolver(config=config)

    def test_invalid_grid_resolution_type(self):
        """Test that list grid resolution works (Python accepts it for indexing)."""
        config = {}
        
        # Python lists work for indexing, so this should not raise
        solver = ShallowWaterSolver(config=config, grid_resolution=[50, 50])
        assert solver.nx == 50
        assert solver.ny == 50

    def test_grid_resolution_too_small(self):
        """Test that grid resolution smaller than (2, 2) raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="grid_resolution must be at least"):
            ShallowWaterSolver(config=config, grid_resolution=(1, 1))

    def test_non_integer_grid_resolution(self):
        """Test that non-integer grid resolution raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="grid_resolution must contain integers"):
            ShallowWaterSolver(config=config, grid_resolution=(50.5, 50))

    def test_non_dict_config(self):
        """Test that non-dict config raises TypeError."""
        with pytest.raises(TypeError, match="config must be a dictionary"):
            ShallowWaterSolver(config="invalid")

    def test_coriolis_can_be_negative(self):
        """Test that negative Coriolis parameter is allowed."""
        config = {"coriolis": -0.0001}
        
        # Should not raise
        solver = ShallowWaterSolver(config=config)
        assert solver.f == -0.0001
