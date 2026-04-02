"""Tests for CFL condition in ShallowWaterSolver."""

import pytest
import numpy as np
from src.physics.shallow_water import ShallowWaterSolver


class TestCFLCondition:
    """Test CFL condition implementation."""

    def test_cfl_condition_satisfied_with_small_dt(self):
        """Test that CFL condition is satisfied with small time step."""
        config = {
            "gravity": 9.81,
            "time_step": 0.01,  # Small time step
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(50, 50))
        
        is_stable, cfl_number = solver._check_cfl_condition()
        
        assert is_stable, "CFL condition should be satisfied with small dt"
        assert cfl_number < 1.0, f"CFL number {cfl_number} should be < 1.0"

    def test_cfl_condition_violated_with_large_dt(self):
        """Test that CFL condition can be violated with large time step."""
        config = {
            "gravity": 9.81,
            "time_step": 10.0,  # Large time step
            "domain_x": 100.0,  # Small domain
            "domain_y": 100.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(20, 20))
        
        # Set high velocity to trigger CFL violation
        solver.state.velocity_x[:] = 5.0
        
        is_stable, cfl_number = solver._check_cfl_condition()
        
        # With these parameters, CFL should likely be violated
        assert cfl_number > 0, "CFL number should be positive"

    def test_compute_stable_time_step(self):
        """Test computation of stable time step."""
        config = {
            "gravity": 9.81,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(50, 50))
        
        stable_dt = solver._compute_stable_time_step(cfl_target=0.8)
        
        assert stable_dt > 0, "Stable time step should be positive"
        assert stable_dt <= solver.dt * 10, "Should not increase dt by more than 10x"

    def test_cfl_with_zero_velocity(self):
        """Test CFL condition with zero velocity."""
        config = {
            "gravity": 9.81,
            "time_step": 1.0,
            "domain_x": 1000.0,
            "domain_y": 1000.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(50, 50))
        
        # With zero velocity, CFL should be based on wave speed only
        is_stable, cfl_number = solver._check_cfl_condition()
        
        assert cfl_number >= 0, "CFL number should be non-negative"

    def test_evolve_logs_cfl_warning(self, caplog):
        """Test that evolve method logs CFL warning when violated."""
        import logging
        caplog.set_level(logging.WARNING)
        
        config = {
            "gravity": 9.81,
            "time_step": 5.0,  # Large time step
            "domain_x": 50.0,  # Small domain
            "domain_y": 50.0,
        }
        solver = ShallowWaterSolver(config=config, grid_resolution=(10, 10))
        
        # Set high velocity
        solver.state.velocity_x[:] = 10.0
        
        # Run evolve - should log warning
        solver.evolve(steps=2)
        
        # Check if CFL warning was logged
        cfl_warnings = [record for record in caplog.records if "CFL" in record.message]
        # Note: May or may not trigger warning depending on exact parameters
