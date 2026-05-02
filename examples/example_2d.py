#!/usr/bin/env python3
"""
Example 2: 2D Floodplain Simulation (FV + HLLE Riemann Solver)
================================================================

Scenario: Synthetic valley terrain with a river channel, subjected to
a localized storm cell rainfall event. Water accumulates in the basin
and drains through the channel.

Demonstrates:
  - 2D terrain generation (synthetic valley with river channel)
  - Open boundary conditions (all four sides)
  - Rainfall source term (Gaussian storm cell)
  - HLLE Riemann solver with MUSCL reconstruction
  - CFL-adaptive time stepping
  - Flood risk classification (none/minor/moderate/major/severe)
  - Mass conservation monitoring

Run:
  python examples/example_2d.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import get_config
from src.physics.engine import SimulationEngine
from src.physics.solver_2d.boundary import BoundaryConditions, BCType


# ── Scenario parameters ──────────────────────────────────────────────────

NX = 60                     # grid cells in x
NY = 60                     # grid cells in y
DX = 100.0                  # [m] cell size x
DY = 100.0                  # [m] cell size y

# Terrain
AMPLITUDE = 2.5             # [m] terrain amplitude
INITIAL_DEPTH = 0.0         # [m] dry start

# Rainfall
RAIN_PATTERN = "storm_cell"  # 'uniform' | 'storm_cell' | 'frontal'
RAIN_INTENSITY = 5e-5        # [m/s] ≈ 180 mm/day
RAIN_SIGMA = 1500.0          # [m] Gaussian spread

# Simulation
TOTAL_STEPS = 150
PRINT_EVERY = 30


def build_bed_terrain(nx: int, ny: int, amplitude: float) -> np.ndarray:
    """
    Build a realistic synthetic floodplain terrain:
      - Parabolic basin (high at edges, low at center)
      - Narrow river channel running N-S through center
      - Gentle southward slope for drainage
      - Small random roughness
    """
    x = np.linspace(-1.0, 1.0, nx)
    y = np.linspace(-1.0, 1.0, ny)
    xx, yy = np.meshgrid(x, y, indexing="ij")

    ridge_h = amplitude * 5.0
    chan_d  = amplitude * 1.5

    # Parabolic bowl — high edges, low center
    r = np.sqrt(xx ** 2 + yy ** 2)
    z = ridge_h * np.clip(r / 0.9, 0.0, 1.0) ** 2

    # River channel incised along center (x=0)
    chan_w = 0.06   # half-width in normalized coords
    z -= chan_d * np.exp(-(xx / chan_w) ** 2)

    # Gentle southward slope for drainage
    z -= 0.5 * (yy + 1.0)

    # Small terrain noise
    rng = np.random.default_rng(42)
    z += 0.2 * rng.standard_normal((nx, ny))

    return np.maximum(z, 0.0)


def apply_rainfall(solver, pattern: str, intensity: float, sigma: float) -> float:
    """Apply rainfall pattern to solver. Returns total rain rate [m3/s]."""
    solver._rain[:] = 0.0
    nx, ny = solver.nx, solver.ny
    dx, dy = solver.dx, solver.dy

    cx = nx * dx / 2
    cy = ny * dy / 2
    x = (np.arange(nx) + 0.5) * dx
    y = (np.arange(ny) + 0.5) * dy
    xx, yy = np.meshgrid(x, y, indexing="ij")

    if pattern == "uniform":
        solver._rain[:] = intensity
    elif pattern == "storm_cell":
        r2 = (xx - cx) ** 2 + (yy - cy) ** 2
        solver._rain[:] = intensity * np.exp(-r2 / (2.0 * sigma ** 2))
    elif pattern == "frontal":
        gradient = x / (nx * dx)
        solver._rain[:] = intensity * gradient[:, np.newaxis]

    return float(np.sum(solver._rain)) * dx * dy


# ── Diagnostics ──────────────────────────────────────────────────────────

def print_header():
    print("=" * 72)
    print("  2D Floodplain Simulation — FV + HLLE Riemann Solver")
    print("=" * 72)
    print(f"  Domain:           {NX} x {NY} cells  ({NX*DX:.0f} x {NY*DY:.0f} m)")
    print(f"  Cell size:        {DX:.0f} x {DY:.0f} m")
    print(f"  Terrain:          Synthetic valley (amplitude {AMPLITUDE:.1f} m)")
    print(f"  Rainfall:         {RAIN_PATTERN} (I={RAIN_INTENSITY*86400:.0f} mm/day)")
    print(f"  Boundaries:       Open (all four sides)")
    print(f"  Steps:            {TOTAL_STEPS}")
    print("=" * 72)
    print()


def print_step(state, solver, step, elapsed):
    h = state.water_depth
    u = state.velocity_x
    v = state.velocity_y

    wet = h > solver.min_depth
    flooded = int(np.sum(wet))
    h_max = float(np.max(h))
    speed_max = float(np.sqrt(np.max(u**2 + v**2)))
    vol = float(np.sum(h)) * solver.dx * solver.dy

    print(
        f"  step {step:>3d}  t={solver.current_time:>7.1f}s  dt={solver.dt:>5.2f}s  "
        f"h_max={h_max:>6.3f}m  speed={speed_max:>5.3f}m/s  "
        f"flooded={flooded:>5d}  vol={vol:>9.1f}m3"
    )


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print_header()

    cfg = get_config()

    # Override config for this example
    cfg.physics.solver_2d.nx = NX
    cfg.physics.solver_2d.ny = NY
    cfg.physics.solver_2d.dx = DX
    cfg.physics.solver_2d.dy = DY
    cfg.terrain.amplitude = AMPLITUDE
    cfg.terrain.initial_water_depth = INITIAL_DEPTH

    bed = build_bed_terrain(NX, NY, AMPLITUDE)
    print(f"  Terrain elevation: {bed.min():.2f} — {bed.max():.2f} m")

    # Open boundaries
    bc = BoundaryConditions(
        west=BCType.OPEN,
        east=BCType.OPEN,
        south=BCType.OPEN,
        north=BCType.OPEN,
    )

    engine = SimulationEngine(mode="2d", config=cfg)
    engine.initialize(
        bed_elevation=bed,
        dx=DX,
        dy=DY,
    )

    solver_2d = engine._solver_2d
    solver_2d.bc = bc

    # Apply rainfall
    rain_rate = apply_rainfall(solver_2d, RAIN_PATTERN, RAIN_INTENSITY, RAIN_SIGMA)
    print(f"  Rainfall rate:     {rain_rate:.4f} m3/s (integrated over domain)")
    print()

    # ── Run simulation ────────────────────────────────────────────────────
    print(
        f"  {'step':>4s}  {'time':>6s}  {'dt':>5s}  "
        f"{'h_max':>6s}  {'speed':>6s}  {'flooded':>7s}  {'vol':>8s}"
    )
    print("  " + "-" * 68)

    start = time.perf_counter()
    for step in range(TOTAL_STEPS):
        state = engine.step()
        if step % PRINT_EVERY == 0 or step == TOTAL_STEPS - 1:
            print_step(state, solver_2d, step, time.perf_counter() - start)
    elapsed = time.perf_counter() - start
    print("  " + "-" * 68)
    print()

    # ── Final state summary ───────────────────────────────────────────────
    state = engine.state
    h = state.water_depth
    risk = state.flood_risk

    wet = h > solver_2d.min_depth
    flooded_cells = int(np.sum(wet))
    flooded_area = flooded_cells * DX * DY / 1e6  # km2
    vol_total = float(np.sum(h)) * DX * DY

    print("  Final State:")
    print(f"    Elapsed time:      {solver_2d.current_time:.1f} s")
    print(f"    Flooded cells:     {flooded_cells} ({flooded_area:.3f} km²)")
    print(f"    Total volume:      {vol_total:.1f} m³")
    print(f"    Max depth:         {np.max(h):.4f} m")
    print(f"    Mass error:        {solver_2d.mass_conservation_error()*100:.2f}%")
    print()

    # Risk distribution
    labels = ["none", "minor", "moderate", "major", "severe"]
    print("  Flood risk distribution:")
    for i, label in enumerate(labels):
        count = int(np.sum(risk == i))
        pct = count / (NX * NY) * 100
        if count > 0:
            print(f"    {label:>10s}: {count:>5d} cells ({pct:.1f}%)")
    print()

    # ── Validation ────────────────────────────────────────────────────────
    print("  Validation:")
    n_pass = 0
    n_total = 0

    # 1. No NaN/Inf
    n_total += 1
    if np.all(np.isfinite(h)):
        print("    [PASS] No NaN/Inf in water depth")
        n_pass += 1
    else:
        print("    [FAIL] NaN/Inf detected")

    # 2. Non-negative depth
    n_total += 1
    if np.all(h >= 0):
        print("    [PASS] All depths non-negative")
        n_pass += 1
    else:
        print(f"    [FAIL] Negative depth found (min={np.min(h):.6f})")

    # 3. Rainfall produced flooding
    n_total += 1
    if flooded_cells > 0:
        print(f"    [PASS] Rainfall produced flooding ({flooded_cells} cells)")
        n_pass += 1
    else:
        print("    [FAIL] No flooding detected")

    # 4. Water pools in low terrain
    n_total += 1
    min_idx = np.unravel_index(np.argmin(bed), bed.shape)
    depth_at_low = h[min_idx]
    if depth_at_low > 0.001:
        print(f"    [PASS] Water pools at terrain low point (h={depth_at_low:.4f} m)")
        n_pass += 1
    else:
        print(f"    [FAIL] No pooling at lowest point (h={depth_at_low:.4f})")

    # 5. Mass conservation
    n_total += 1
    mass_err = solver_2d.mass_conservation_error()
    if mass_err < 0.15:
        print(f"    [PASS] Mass conservation: {mass_err*100:.2f}% error (< 15%)")
        n_pass += 1
    else:
        print(f"    [FAIL] Mass conservation error too high: {mass_err*100:.2f}%")

    # 6. Physical velocity bound
    n_total += 1
    max_speed = float(np.sqrt(np.max(state.velocity_x**2 + state.velocity_y**2)))
    if max_speed < 15.0:
        print(f"    [PASS] Max speed {max_speed:.3f} m/s < 15 m/s")
        n_pass += 1
    else:
        print(f"    [FAIL] Excessive speed: {max_speed:.3f} m/s")

    # 7. Performance
    print(f"\n    [INFO] Performance: {TOTAL_STEPS/elapsed:.1f} steps/s ({elapsed:.3f}s total)")

    print()
    print(f"  Result: {n_pass}/{n_total} checks passed")
    print("=" * 72)


if __name__ == "__main__":
    main()
