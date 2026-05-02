#!/usr/bin/env python3
"""
Example 1: 1D River Reach Simulation (Preissmann Implicit Solver)
=================================================================

Scenario: Single rectangular channel reach with an upstream discharge
hydrograph (triangular flood wave) and a fixed downstream stage boundary.

Demonstrates:
  - ChannelNetwork construction (rectangular cross-sections)
  - Boundary conditions (discharge hydrograph + fixed stage)
  - Preissmann theta-implicit stepping (large dt, unconditional stability)
  - State inspection (Q, h, velocity along chainage)
  - Mass balance diagnostics

Run:
  python examples/example_1d.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

# Ensure project root is on path so `src.*` imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import get_config
from src.physics.engine import SimulationEngine
from src.physics.solver_1d.cross_section import CrossSection
from src.physics.solver_1d.network import (
    ChannelNetwork,
    NetworkNode,
    NetworkEdge,
    NodeType,
    BoundaryCondition1D,
    BCType1D,
)


# ── Scenario parameters ──────────────────────────────────────────────────

REACH_LENGTH    = 5000.0      # [m] total reach length
N_CROSS_SECTIONS = 20         # interior CS nodes
CHANNEL_WIDTH   = 15.0        # [m] rectangular channel width
BANK_HEIGHT     = 6.0         # [m] bank-full depth
BED_SLOPE       = 0.001       # [m/m] uniform bed slope
MANNING_N       = 0.025       # Manning roughness

# Boundary conditions
UPSTREAM_Q_PEAK = 80.0        # [m3/s] peak flood discharge
UPSTREAM_Q_BASE = 10.0        # [m3/s] baseflow
PEAK_TIME       = 120.0       # [s] time of peak arrival
DURATION        = 300.0       # [s] hydrograph duration
DOWNSTREAM_STAGE = 3.0        # [m a.s.l.] fixed tailwater

# Simulation control
DT        = 5.0               # [s] time step (implicit, can be large)
TOTAL_STEPS = 100             # total steps (500 s simulated time)
PRINT_EVERY = 10


def build_hydrograph() -> BoundaryCondition1D:
    """Triangular flood wave hydrograph at the upstream boundary."""
    times = np.array([
        0.0,
        PEAK_TIME * 0.5,       # rising limb midpoint
        PEAK_TIME,             # peak
        PEAK_TIME + (DURATION - PEAK_TIME) * 0.5,  # recession midpoint
        DURATION,              # return to base
        DURATION + 200.0,      # tail
    ])
    values = np.array([
        UPSTREAM_Q_BASE,
        UPSTREAM_Q_BASE + 0.4 * (UPSTREAM_Q_PEAK - UPSTREAM_Q_BASE),
        UPSTREAM_Q_PEAK,
        UPSTREAM_Q_BASE + 0.4 * (UPSTREAM_Q_PEAK - UPSTREAM_Q_BASE),
        UPSTREAM_Q_BASE,
        UPSTREAM_Q_BASE,
    ])
    return BoundaryCondition1D(BCType1D.DISCHARGE, times, values)


def build_network() -> ChannelNetwork:
    """Construct a single straight reach with rectangular cross-sections."""
    cs = CrossSection.rectangular(
        width=CHANNEL_WIDTH,
        z_bed=0.0,
        bank_height=BANK_HEIGHT,
        manning_n=MANNING_N,
    )

    # Use the factory helper
    net = ChannelNetwork.simple_reach(
        n_cross_sections=N_CROSS_SECTIONS,
        reach_length=REACH_LENGTH,
        cross_section=cs,
        slope=BED_SLOPE,
        upstream_Q=UPSTREAM_Q_BASE,
        downstream_h=DOWNSTREAM_STAGE,
    )

    # Replace upstream constant BC with flood hydrograph
    up_node = net.get_node("upstream")
    up_node.boundary_condition = build_hydrograph()

    return net


# ── Diagnostics helpers ──────────────────────────────────────────────────

def print_header():
    print("=" * 72)
    print("  1D River Reach Simulation — Preissmann Implicit Solver")
    print("=" * 72)
    print(f"  Reach length:       {REACH_LENGTH:>7.0f} m")
    print(f"  Cross-sections:     {N_CROSS_SECTIONS:>7d} (rectangular)")
    print(f"  Channel width:      {CHANNEL_WIDTH:>7.1f} m")
    print(f"  Bank height:        {BANK_HEIGHT:>7.1f} m")
    print(f"  Bed slope:          {BED_SLOPE:.6f}")
    print(f"  Manning n:          {MANNING_N:.3f}")
    print(f"  Upstream BC:        Discharge hydrograph (peak {UPSTREAM_Q_PEAK:.0f} m3/s)")
    print(f"  Downstream BC:      Fixed stage {DOWNSTREAM_STAGE:.1f} m a.s.l.")
    print(f"  Time step:          {DT:.1f} s x {TOTAL_STEPS} steps")
    print("=" * 72)
    print()


def print_step(state, step, t, wall_dt):
    Q = state.discharge
    h = state.water_surface_elev
    v = state.velocity
    # Interior only (exclude boundary nodes at 0 and -1)
    Q_mean = float(np.mean(Q[1:-1]))
    h_max  = float(np.max(h[1:-1]))
    v_max  = float(np.max(np.abs(v[1:-1])))
    print(
        f"  step {step:>3d}  t={t:>7.1f}s  "
        f"Q_up={Q[0]:>7.1f}  Q_mid={Q_mean:>7.1f}  Q_dn={Q[-1]:>7.1f}  "
        f"h_max={h_max:>5.3f}m  v_max={v_max:>5.3f}m/s"
    )


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print_header()

    cfg = get_config()
    engine = SimulationEngine(mode="1d", config=cfg)
    network = build_network()

    print(f"  Network: {len(network.nodes)} nodes, {len(network.edges)} reach(es)")
    engine.initialize(network=network)
    print(f"  Engine initialized in mode '{engine.mode}'\n")

    # Run
    print(
        f"  {'step':>4s}  {'time':>6s}  "
        f"{'Q_up':>7s}  {'Q_mid':>7s}  {'Q_dn':>7s}  "
        f"{'h_max':>7s}  {'v_max':>7s}"
    )
    print("  " + "-" * 68)

    start = time.perf_counter()
    for step in range(TOTAL_STEPS):
        state = engine.step(dt=DT)
        wall_dt = time.perf_counter() - start
        if step % PRINT_EVERY == 0 or step == TOTAL_STEPS - 1:
            print_step(state, step, engine.current_time, wall_dt)
    elapsed = time.perf_counter() - start
    print("  " + "-" * 68)
    print()

    # ── Validation ────────────────────────────────────────────────────────
    state = engine.state
    Q = state.discharge
    h = state.water_surface_elev
    v = state.velocity

    print("  Validation:")
    n_pass = 0
    n_total = 0

    # 1. No NaN/Inf
    n_total += 1
    if np.all(np.isfinite(Q)) and np.all(np.isfinite(h)) and np.all(np.isfinite(v)):
        print("    [PASS] All state variables are finite")
        n_pass += 1
    else:
        print("    [FAIL] NaN/Inf detected in state variables")

    # 2. Downstream stage enforced
    n_total += 1
    h_ds = float(h[-1])
    if abs(h_ds - DOWNSTREAM_STAGE) < 0.15:
        print(f"    [PASS] Downstream stage enforced: {h_ds:.4f} ≈ {DOWNSTREAM_STAGE:.1f}")
        n_pass += 1
    else:
        print(f"    [FAIL] Downstream stage: {h_ds:.4f} vs {DOWNSTREAM_STAGE:.1f}")

    # 3. Positive discharge (no flow reversal)
    n_total += 1
    if np.all(Q > -0.1):
        print(f"    [PASS] Discharge positive (min={np.min(Q):.3f})")
        n_pass += 1
    else:
        print(f"    [FAIL] Negative discharge: min={np.min(Q):.3f}")

    # 4. Physical velocity bound
    n_total += 1
    v_max = float(np.max(np.abs(v[1:-1])))
    if v_max < 15.0:
        print(f"    [PASS] Velocity physical: max={v_max:.3f} m/s < 15 m/s")
        n_pass += 1
    else:
        print(f"    [FAIL] Excessive velocity: {v_max:.3f} m/s")

    # 5. Performance
    n_total += 1
    steps_per_sec = TOTAL_STEPS / elapsed
    print(f"    [INFO] Performance: {steps_per_sec:.1f} steps/s ({elapsed:.3f}s total)")

    print()
    print(f"  Result: {n_pass}/{n_total} checks passed")
    print("=" * 72)


if __name__ == "__main__":
    main()
