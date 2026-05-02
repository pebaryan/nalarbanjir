#!/usr/bin/env python3
"""Performance benchmarks for the Nalarbanjir flood prediction solver.

Measures:
  - Physics engine step throughput (steps/sec)
  - Memory usage during simulation
  - ML inference latency
  - Feature extraction speed
  - Mesh generation time

Usage:
  python benchmarks/solver_benchmark.py [--gpu]
"""

import argparse
import sys
import time
import tracemalloc
import numpy as np
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.physics.flood_physics_3d import FloodPhysicsEngine3D
from src.ml.features import extract_features, normalise_features
from src.ml.model import FloodNet, ModelConfig


def benchmark_physics_step(grid_size: tuple[int, int], num_steps: int = 1000):
    """Benchmark physics engine step throughput."""
    print(f"\n{'='*60}")
    print(f"Physics Engine Benchmark: {grid_size[0]}x{grid_size[1]} grid")
    print(f"{'='*60}")

    engine = FloodPhysicsEngine3D(grid_size=grid_size, dx=10.0)

    # Generate terrain (valley shape)
    nx, ny = grid_size
    y = np.arange(ny)
    yy, xx = np.meshgrid(y, y, indexing="ij")
    center = nx / 2
    elevation = 10 * ((xx - center) ** 2 + (yy - center) ** 2) / (center ** 2)
    engine.set_terrain(elevation)

    # Add water source
    engine.add_initial_water_source(x=nx // 3, y=ny // 3, depth=3.0, radius=8)

    # Warmup
    for _ in range(10):
        engine.step()

    # Benchmark
    start = time.perf_counter()
    for _ in range(num_steps):
        engine.step()
    elapsed = time.perf_counter() - start

    steps_per_sec = num_steps / elapsed
    ms_per_step = elapsed / num_steps * 1000

    print(f"  Steps:          {num_steps}")
    print(f"  Time:           {elapsed:.3f}s")
    print(f"  Steps/sec:      {steps_per_sec:.1f}")
    print(f"  ms/step:        {ms_per_step:.2f}")
    print(f"  Final max depth: {engine.get_maximum_depth():.3f} m")
    print(f"  Flood extent:    {engine.get_flood_extent():.0f} m²")

    return steps_per_sec


def benchmark_ml_inference(grid_size: tuple[int, int], batch_size: int = 256):
    """Benchmark ML inference latency."""
    print(f"\n{'='*60}")
    print(f"ML Inference Benchmark: {grid_size[0]}x{grid_size[1]} grid")
    print(f"{'='*60}")

    try:
        import torch
    except ImportError:
        print("  Skipped: PyTorch not available")
        return None

    config = ModelConfig(input_features=10, hidden_dims=[64, 128, 256], output_features=5)
    model = FloodNet(config)
    model.eval()

    # Create synthetic state-like data
    nx, ny = grid_size
    n_cells = nx * ny

    # Generate features
    features = np.random.randn(n_cells, 10).astype(np.float32)
    X = torch.FloatTensor(features)

    # Warmup
    for _ in range(5):
        with torch.no_grad():
            out, _ = model(X.unsqueeze(1))

    # Benchmark
    start = time.perf_counter()
    num_runs = 50
    for _ in range(num_runs):
        with torch.no_grad():
            out, _ = model(X.unsqueeze(1))
        torch.cuda.synchronize() if torch.cuda.is_available() else None
    elapsed = time.perf_counter() - start

    ms_per_inference = elapsed / num_runs * 1000

    print(f"  Cells:          {n_cells:,}")
    print(f"  Runs:           {num_runs}")
    print(f"  ms/inference:   {ms_per_inference:.2f}")
    print(f"  Throughput:     {num_runs / elapsed * 1000:.0f} inferences/sec")

    return ms_per_inference


def benchmark_feature_extraction(grid_size: tuple[int, int]):
    """Benchmark feature extraction speed."""
    print(f"\n{'='*60}")
    print(f"Feature Extraction Benchmark: {grid_size[0]}x{grid_size[1]} grid")
    print(f"{'='*60}")

    nx, ny = grid_size

    # Create a mock Solver2DState-like object
    class MockState:
        def __init__(self):
            self.water_depth = np.random.uniform(0, 3, (nx, ny)).astype(np.float32)
            self.velocity_x = np.random.uniform(-2, 2, (nx, ny)).astype(np.float32)
            self.velocity_y = np.random.uniform(-2, 2, (nx, ny)).astype(np.float32)
            self.bed_elevation = np.random.uniform(0, 50, (nx, ny)).astype(np.float32)
            self.flood_risk = np.random.randint(0, 5, (nx, ny)).astype(np.int8)
            self.nx = nx
            self.ny = ny

    state = MockState()

    # Warmup
    for _ in range(5):
        extract_features(state)

    # Benchmark
    start = time.perf_counter()
    num_runs = 100
    for _ in range(num_runs):
        features = extract_features(state)
    elapsed = time.perf_counter() - start

    ms_per_extract = elapsed / num_runs * 1000
    cells = nx * ny
    ms_per_cell = ms_per_extract / cells * 1000

    print(f"  Cells:          {cells:,}")
    print(f"  Runs:           {num_runs}")
    print(f"  ms/extraction:  {ms_per_extract:.3f}")
    print(f"  μs/cell:        {ms_per_cell:.3f}")

    return ms_per_extract


def benchmark_normalisation(grid_size: tuple[int, int]):
    """Benchmark feature normalisation speed."""
    print(f"\n{'='*60}")
    print(f"Normalisation Benchmark: {grid_size[0]}x{grid_size[1]} grid")
    print(f"{'='*60}")

    nx, ny = grid_size
    features = np.random.randn(nx * ny, 10).astype(np.float32)

    # Warmup
    for _ in range(5):
        normalise_features(features)

    # Benchmark
    start = time.perf_counter()
    num_runs = 100
    for _ in range(num_runs):
        normalise_features(features)
    elapsed = time.perf_counter() - start

    ms_per_run = elapsed / num_runs * 1000

    print(f"  Cells:          {nx * ny:,}")
    print(f"  Runs:           {num_runs}")
    print(f"  ms/normalise:   {ms_per_run:.4f}")

    return ms_per_run


def benchmark_memory(grid_size: tuple[int, int], num_steps: int = 100):
    """Benchmark memory usage."""
    print(f"\n{'='*60}")
    print(f"Memory Benchmark: {grid_size[0]}x{grid_size[1]} grid, {num_steps} steps")
    print(f"{'='*60}")

    tracemalloc.start()

    engine = FloodPhysicsEngine3D(grid_size=grid_size, dx=10.0)
    engine.set_terrain(np.random.uniform(0, 20, grid_size))
    engine.add_initial_water_source(x=grid_size[0] // 2, y=grid_size[1] // 2, depth=2.0, radius=5)

    snapshot_before = tracemalloc.take_snapshot()

    for _ in range(num_steps):
        engine.step()

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Compare snapshots
    stats = snapshot_after.compare_to(snapshot_before, 'lineno')
    total_diff = sum(s.size_diff for s in stats[:10])

    current, peak = tracemalloc.get_traced_memory() if False else (0, 0)

    print(f"  Grid cells:     {grid_size[0] * grid_size[1]:,}")
    print(f"  Steps run:      {num_steps}")
    print(f"  Top allocators: ")
    for stat in stats[:5]:
        print(f"    {stat}")


def main():
    parser = argparse.ArgumentParser(description="Nalarbanjir Performance Benchmarks")
    parser.add_argument("--grid", type=int, nargs=2, default=[100, 100],
                        help="Grid size (default: 100 100)")
    parser.add_argument("--steps", type=int, default=1000, help="Physics steps (default: 1000)")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    args = parser.parse_args()

    grid = tuple(args.grid)

    print("=" * 60)
    print("  Nalarbanjir Performance Benchmarks")
    print(f"  Grid: {grid[0]}x{grid[1]}, Cells: {grid[0]*grid[1]:,}")
    print("=" * 60)

    # Always run physics benchmark
    physics_sps = benchmark_physics_step(grid, args.steps)

    if args.all:
        benchmark_ml_inference(grid)
        benchmark_feature_extraction(grid)
        benchmark_normalisation(grid)
        benchmark_memory(grid)
    else:
        benchmark_feature_extraction(grid)

    print(f"\n{'='*60}")
    print("  Benchmarks complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
