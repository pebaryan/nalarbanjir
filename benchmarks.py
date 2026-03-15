"""Performance benchmarks for flood prediction simulation.

This module provides benchmarking tools to measure the performance
of different components of the flood prediction system.
"""

import time
import numpy as np
import sys
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.append("src")

from physics.shallow_water import ShallowWaterSolver
from physics.terrain import TerrainModel
from ml.model import FloodNet, ModelConfig


class PerformanceBenchmark:
    """Benchmark suite for flood prediction components."""

    def __init__(self):
        """Initialize benchmark suite."""
        self.results = {}

    def benchmark_physics_solver(
        self,
        grid_sizes: List[Tuple[int, int]] = [(50, 50), (100, 100), (200, 200)],
        steps: int = 100,
    ) -> Dict:
        """Benchmark physics solver performance.

        Args:
            grid_sizes: List of grid sizes to test
            steps: Number of simulation steps

        Returns:
            Benchmark results dictionary
        """
        logger.info("=" * 60)
        logger.info("PHYSICS SOLVER BENCHMARK")
        logger.info("=" * 60)

        results = {}
        config = {
            "gravity": 9.81,
            "coriolis": 0.0,
            "bottom_friction": 0.02,
            "time_step": 1.0,
            "domain_x": 10000.0,
            "domain_y": 10000.0,
        }

        for nx, ny in grid_sizes:
            logger.info(f"\nTesting grid size: {nx}x{ny}")

            # Initialize solver
            start_time = time.time()
            solver = ShallowWaterSolver(config=config, grid_resolution=(nx, ny))
            init_time = time.time() - start_time

            # Run simulation
            start_time = time.time()
            states = solver.evolve(steps=steps)
            sim_time = time.time() - start_time

            # Calculate metrics
            total_cells = nx * ny
            cells_per_second = (total_cells * steps) / sim_time
            time_per_step = sim_time / steps

            results[f"{nx}x{ny}"] = {
                "grid_size": (nx, ny),
                "total_cells": total_cells,
                "steps": steps,
                "init_time": init_time,
                "simulation_time": sim_time,
                "time_per_step": time_per_step,
                "cells_per_second": cells_per_second,
            }

            logger.info(f"  Initialization: {init_time:.4f}s")
            logger.info(f"  Simulation: {sim_time:.4f}s")
            logger.info(f"  Time per step: {time_per_step:.4f}s")
            logger.info(f"  Throughput: {cells_per_second:,.0f} cells/second")

        self.results["physics_solver"] = results
        return results

    def benchmark_terrain_model(
        self,
        resolutions: List[Tuple[int, int]] = [(100, 100), (500, 500), (1000, 1000)],
    ) -> Dict:
        """Benchmark terrain model performance.

        Args:
            resolutions: List of resolutions to test

        Returns:
            Benchmark results dictionary
        """
        logger.info("\n" + "=" * 60)
        logger.info("TERRAIN MODEL BENCHMARK")
        logger.info("=" * 60)

        results = {}
        config = {
            "flood_thresholds": {
                "minor": 1.0,
                "moderate": 2.0,
                "major": 3.0,
                "severe": 5.0,
            }
        }

        for nx, ny in resolutions:
            logger.info(f"\nTesting resolution: {nx}x{ny}")

            # Initialize terrain
            start_time = time.time()
            terrain = TerrainModel(config=config, resolution=(nx, ny))
            init_time = time.time() - start_time

            # Test flood zone computation
            water_depth = np.random.rand(ny, nx) * 3.0
            start_time = time.time()
            flood_zones = terrain.get_flood_zones(water_depth)
            flood_time = time.time() - start_time

            # Test export
            start_time = time.time()
            terrain_data = terrain.export_terrain_data()
            export_time = time.time() - start_time

            results[f"{nx}x{ny}"] = {
                "resolution": (nx, ny),
                "total_cells": nx * ny,
                "init_time": init_time,
                "flood_zone_time": flood_time,
                "export_time": export_time,
            }

            logger.info(f"  Initialization: {init_time:.4f}s")
            logger.info(f"  Flood zone computation: {flood_time:.4f}s")
            logger.info(f"  Data export: {export_time:.4f}s")

        self.results["terrain_model"] = results
        return results

    def benchmark_ml_model(
        self, input_sizes: List[int] = [10, 100, 1000], num_predictions: int = 100
    ) -> Dict:
        """Benchmark ML model performance.

        Args:
            input_sizes: List of batch sizes to test
            num_predictions: Number of predictions per test

        Returns:
            Benchmark results dictionary
        """
        logger.info("\n" + "=" * 60)
        logger.info("ML MODEL BENCHMARK")
        logger.info("=" * 60)

        results = {}
        config = ModelConfig()

        # Initialize model
        start_time = time.time()
        model = FloodNet(config)
        model.eval()
        init_time = time.time() - start_time

        logger.info(f"Model initialization: {init_time:.4f}s")
        logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

        import torch

        for batch_size in input_sizes:
            logger.info(f"\nTesting batch size: {batch_size}")

            # Prepare input
            seq_len = 1
            input_tensor = torch.randn(batch_size, seq_len, config.input_features)

            # Warmup
            with torch.no_grad():
                for _ in range(10):
                    _ = model(input_tensor)

            # Benchmark
            start_time = time.time()
            with torch.no_grad():
                for _ in range(num_predictions):
                    output, _ = model(input_tensor)
            total_time = time.time() - start_time

            predictions_per_second = (batch_size * num_predictions) / total_time
            time_per_prediction = total_time / num_predictions

            results[f"batch_{batch_size}"] = {
                "batch_size": batch_size,
                "num_predictions": num_predictions,
                "total_time": total_time,
                "time_per_prediction": time_per_prediction,
                "predictions_per_second": predictions_per_second,
            }

            logger.info(f"  Total time: {total_time:.4f}s")
            logger.info(f"  Time per batch: {time_per_prediction:.4f}s")
            logger.info(
                f"  Throughput: {predictions_per_second:,.0f} predictions/second"
            )

        self.results["ml_model"] = results
        return results

    def run_all_benchmarks(self) -> Dict:
        """Run all benchmarks.

        Returns:
            Complete benchmark results
        """
        logger.info("\n" + "=" * 60)
        logger.info("FLOOD PREDICTION PERFORMANCE BENCHMARKS")
        logger.info("=" * 60)

        self.benchmark_physics_solver()
        self.benchmark_terrain_model()
        self.benchmark_ml_model()

        logger.info("\n" + "=" * 60)
        logger.info("BENCHMARKS COMPLETED")
        logger.info("=" * 60)

        return self.results

    def print_summary(self):
        """Print benchmark summary."""
        logger.info("\n" + "=" * 60)
        logger.info("BENCHMARK SUMMARY")
        logger.info("=" * 60)

        if "physics_solver" in self.results:
            logger.info("\nPhysics Solver:")
            for grid, data in self.results["physics_solver"].items():
                logger.info(f"  {grid}: {data['cells_per_second']:,.0f} cells/s")

        if "terrain_model" in self.results:
            logger.info("\nTerrain Model:")
            for res, data in self.results["terrain_model"].items():
                logger.info(f"  {res}: {data['init_time']:.4f}s init")

        if "ml_model" in self.results:
            logger.info("\nML Model:")
            for batch, data in self.results["ml_model"].items():
                logger.info(f"  {batch}: {data['predictions_per_second']:,.0f} pred/s")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()
    benchmark.print_summary()
