"""Integration tests for the full flood prediction workflow.

These tests verify that all components work together correctly
in an end-to-end simulation scenario.
"""

import numpy as np
import pytest
import sys

sys.path.append("src")

from physics.shallow_water import ShallowWaterSolver, WavePropagationAnalyzer
from physics.terrain import TerrainModel
from ml.model import MLModel, ModelConfig
from visualization.renderer import VisualizationRenderer
from visualization.water_surface import WaterSurfaceRenderer
from visualization.flow_vectors import FlowVectorRenderer
from visualization.flood_zones import FloodZoneMapper


class TestFullWorkflow:
    """Integration tests for the complete flood prediction workflow."""

    def test_complete_simulation_pipeline(self):
        """Test the complete simulation pipeline from physics to visualization."""
        # Step 1: Initialize terrain
        terrain_config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }
        terrain = TerrainModel(config=terrain_config, resolution=(50, 50))

        # Step 2: Initialize physics solver
        physics_config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 0.5,
            "domain_x": 5000.0,
            "domain_y": 5000.0,
        }
        solver = ShallowWaterSolver(config=physics_config, grid_resolution=(50, 50))

        # Step 3: Run simulation
        states = solver.evolve(steps=10)
        assert len(states) == 11  # Initial + 10 steps

        # Step 4: Analyze wave propagation
        analyzer = WavePropagationAnalyzer(solver)
        wave_analysis = analyzer.analyze_wave_propagation(states[-1])

        assert "celerity" in wave_analysis
        assert "propagation_angle" in wave_analysis
        assert "kinetic_energy" in wave_analysis
        assert "potential_energy" in wave_analysis

        # Step 5: Identify flood zones
        flood_zones = terrain.get_flood_zones(solver.state.depth)
        assert isinstance(flood_zones, dict)

        # Step 6: Generate ML predictions
        ml_config = ModelConfig()
        ml_model = MLModel(ml_config)
        predictions = ml_model.predict(prediction_type="flood_risk", horizon=24)

        assert isinstance(predictions, dict)

        # Step 7: Visualize results
        vis_config = {
            "color_schemes": {
                "natural": {
                    "water": "#3b82f6",
                    "risk": {
                        "low": "#10b981",
                        "moderate": "#f59e0b",
                        "high": "#ef4444",
                        "severe": "#7f1d1d",
                    },
                }
            },
            "components": {
                "flow_vectors": {"vector_density": 0.5, "max_vector_length": 50.0}
            },
        }
        renderer = VisualizationRenderer(vis_config)
        render_output = renderer.render(solver, terrain, output_format="full")

        # Full format wraps everything under 'visualization' key
        assert "visualization" in render_output
        vis_data = render_output["visualization"]
        assert "water_surface" in vis_data
        assert "flow_vectors" in vis_data
        assert "flood_zones" in vis_data
        assert "metadata" in vis_data

        print("✓ Complete simulation pipeline test passed")

    def test_component_interactions(self):
        """Test that components can exchange data correctly."""
        # Create components with matching grid sizes
        grid_size = (30, 30)

        terrain = TerrainModel(
            config={"flood_thresholds": {"minor": 1.0, "moderate": 2.0}},
            resolution=grid_size,
        )

        solver = ShallowWaterSolver(
            config={"gravity": 9.81, "time_step": 1.0}, grid_resolution=grid_size
        )

        # Verify grid compatibility
        assert terrain.nx == solver.nx
        assert terrain.ny == solver.ny

        # Test data exchange
        water_surface = solver.get_water_surface()
        assert water_surface.shape == (grid_size[1], grid_size[0])

        velocity_x, velocity_y = solver.get_velocity_field()
        assert velocity_x.shape == (grid_size[1], grid_size[0])
        assert velocity_y.shape == (grid_size[1], grid_size[0])

        # Test terrain data export
        terrain_data = terrain.export_terrain_data()
        assert terrain_data["resolution"]["nx"] == grid_size[0]
        assert terrain_data["resolution"]["ny"] == grid_size[1]

        print("✓ Component interactions test passed")

    def test_end_to_end_prediction_workflow(self):
        """Test the complete ML prediction workflow."""
        # Initialize physics and terrain
        terrain = TerrainModel(config={}, resolution=(20, 20))
        solver = ShallowWaterSolver(config={}, grid_resolution=(20, 20))

        # Run simulation to generate state
        states = solver.evolve(steps=5)

        # Get current water depth
        water_depth = solver.state.depth

        # Analyze terrain with water data
        flood_zones = terrain.get_flood_zones(water_depth)

        # Generate predictions
        ml_config = ModelConfig()
        ml_model = MLModel(ml_config)

        predictions = ml_model.predict(prediction_type="flood_risk", horizon=24)

        # Verify predictions have expected structure (has risk levels or confidence)
        assert (
            "low" in predictions
            or "moderate" in predictions
            or "confidence" in predictions
        )

        # Test model state
        model_state = ml_model.get_model_state()
        assert isinstance(model_state, dict)

        print("✓ End-to-end prediction workflow test passed")

    def test_visualization_components(self):
        """Test that visualization components render correctly."""
        grid_size = (25, 25)

        terrain = TerrainModel(config={}, resolution=grid_size)
        solver = ShallowWaterSolver(config={}, grid_resolution=grid_size)

        # Run simulation
        solver.evolve(steps=5)

        # Get data for visualization
        water_surface = solver.get_water_surface()
        velocity_x, velocity_y = solver.get_velocity_field()
        water_depth = solver.state.depth

        # Test water surface renderer
        vis_config = {"color_schemes": {"natural": {"water": "#3b82f6"}}}
        water_renderer = WaterSurfaceRenderer(vis_config)
        water_render = water_renderer.render(water_surface, solver.state.elevation)

        assert water_render["type"] == "water_surface"
        assert "data" in water_render

        # Test flow vector renderer
        flow_renderer = FlowVectorRenderer(vis_config)
        flow_render = flow_renderer.render(velocity_x, velocity_y, water_surface)

        assert flow_render["type"] == "flow_vectors"
        assert "vectors" in flow_render

        # Test flood zone mapper
        zone_mapper = FloodZoneMapper(vis_config)
        zone_render = zone_mapper.render(terrain, water_surface, water_depth)

        assert zone_render["type"] == "flood_zones"
        assert "zones" in zone_render

        print("✓ Visualization components test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
