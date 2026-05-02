#!/usr/bin/env python3
"""
Example 3: 1D+2D Coupled Simulation — Channel Overflow onto Floodplain
========================================================================

Scenario:
  A 1D river channel running through a 2D floodplain. The channel has a
  flood wave propagating downstream. When the water surface exceeds the
  bank elevation, water spills laterally onto the 2D floodplain via a
  broad-crested weir formula.

Demonstrates:
  - 1D+2D coupled simulation engine
  - Channel network + 2D terrain with consistent geometry
  - BankInterface: mapping 1D nodes to 2D grid cells
  - Lateral exchange via broad-crested weir formula
  - Both solvers stepping together (1D advances, exchange computed, 2D advances)
  - CoupledState inspection (state_1d, state_2d, exchange_flux)

Run:
  python examples/example_1d2d.py
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
from src.physics.coupled.interface import BankInterface, InterfacePoint
from src.physics.solver_1d.cross_section import CrossSection
from src.physics.solver_1d.network import (
    ChannelNetwork,
    BoundaryCondition1D,
    BCType1D,
)


# ── Scenario parameters ──────────────────────────────────────────────────

# 1D channel
REACH_LENGTH     = 2000.0    # [m] reach length
N_CROSS_SECTIONS = 12        # interior cross-sections
CHANNEL_WIDTH    = 10.0      # [m] rectangular channel width
BANK_HEIGHT_CS   = 4.0       # [m] bank-full depth (cross-section geometry)
BED_SLOPE        = 0.001     # [m/m]
MANNING_N        = 0.025     # Manning roughness

# Upstream hydrograph (significant flood to trigger overflow)
UPSTREAM_Q_PEAK  = 80.0      # [m3/s] peak discharge
UPSTREAM_Q_BASE  = 5.0       # [m3/s] baseflow
PEAK_TIME        = 100.0     # [s] peak arrival
DURATION         = 250.0     # [s]

DOWNSTREAM_STAGE = 2.0       # [m a.s.l.] fixed tailwater

# 2D floodplain
NX               = 50        # grid cells in x
NY               = 50        # grid cells in y
DX               = 100.0     # [m]
DY               = 100.0     # [m]

# Interface: bank elevation where overflow begins
# Initial WSE range: 2.15 — 3.85 m. Peak WSE ≈ 4.4 m.
# Set bank just below peak so only a brief overflow occurs.
BANK_ELEVATION_Z = 4.3       # [m a.s.l.] weir crest

# Simulation
TOTAL_STEPS      = 80
DT               = 5.0       # [s]
PRINT_EVERY      = 10


def build_hydrograph() -> BoundaryCondition1D:
    """Triangular flood wave."""
    times = np.array([
        0.0,
        PEAK_TIME * 0.4,
        PEAK_TIME,
        PEAK_TIME + (DURATION - PEAK_TIME) * 0.5,
        DURATION,
        DURATION + 100.0,
    ])
    values = np.array([
        UPSTREAM_Q_BASE,
        UPSTREAM_Q_BASE + 0.4 * (UPSTREAM_Q_PEAK - UPSTREAM_Q_BASE),
        UPSTREAM_Q_PEAK,
        UPSTREAM_Q_BASE + 0.3 * (UPSTREAM_Q_PEAK - UPSTREAM_Q_BASE),
        UPSTREAM_Q_BASE,
        UPSTREAM_Q_BASE,
    ])
    return BoundaryCondition1D(BCType1D.DISCHARGE, times, values)


def build_network() -> ChannelNetwork:
    """Single rectangular reach with flood hydrograph upstream."""
    cs = CrossSection.rectangular(
        width=CHANNEL_WIDTH,
        z_bed=0.0,
        bank_height=BANK_HEIGHT_CS,
        manning_n=MANNING_N,
    )

    net = ChannelNetwork.simple_reach(
        n_cross_sections=N_CROSS_SECTIONS,
        reach_length=REACH_LENGTH,
        cross_section=cs,
        slope=BED_SLOPE,
        upstream_Q=UPSTREAM_Q_BASE,
        downstream_h=DOWNSTREAM_STAGE,
    )

    # Replace upstream BC with flood hydrograph
    up_node = net.get_node("upstream")
    up_node.boundary_condition = build_hydrograph()

    return net


def build_bed_terrain(nx: int, ny: int) -> np.ndarray:
    """
    Build 2D terrain with a river channel carved through center.

    The channel runs along x = nx//2 (center of grid), aligned with
    the 1D network's y-direction. Floodplain rises gently away from
    channel. Bed elevations are in local meters (0 at channel bottom).

    The BankInterface compares WSE_1d (absolute m a.s.l.) with
    WSE_2d = bed_elevation + water_depth. To make the weir formula
    work correctly, we set bank_elevations in the interface to match
    the absolute WSE threshold, and the 2D bed + floodplain depths
    will be relative.
    """
    x = np.linspace(-1.0, 1.0, nx)
    y = np.linspace(-1.0, 1.0, ny)
    xx, yy = np.meshgrid(x, y, indexing="ij")

    # Floodplain: gentle rise away from channel centerline
    dist_from_channel = abs(xx)
    z = 4.0 * dist_from_channel ** 2   # quadratic floodplain rise

    # Carve channel at center
    chan_w = 0.03   # half-width in normalized coords
    chan_depth = 2.0   # channel incision depth
    z -= chan_depth * np.exp(-(xx / chan_w) ** 2)

    # Gentle southward slope for drainage
    z -= 0.3 * (yy + 1.0)

    # Small noise
    rng = np.random.default_rng(42)
    z += 0.1 * rng.standard_normal((nx, ny))

    return np.maximum(z, 0.0)


def build_interface(
    network: ChannelNetwork,
    nx: int, ny: int,
    bank_elevation: float,
) -> BankInterface:
    """
    Build a BankInterface that maps 1D cross-section nodes to 2D grid cells
    on both sides of the channel.

    To keep exchange magnitudes manageable, only use interior nodes (avoid
    the boundary nodes at chainage=0 and chainage=length).
    """
    reach_nodes = network.get_reach_nodes("r0")
    node_ids_in_reach = network.edges["r0"].node_ids
    cs_nodes = [n for n in reach_nodes if n.cross_section is not None]

    total_length = reach_nodes[-1].chainage
    if total_length <= 0 or not cs_nodes:
        return BankInterface(points=[])

    i_channel = nx // 2
    points: list[InterfacePoint] = []

    # Use only middle 50% of cross-sections to limit exchange magnitude
    n_cs = len(cs_nodes)
    start_idx = n_cs // 4
    end_idx = 3 * n_cs // 4
    cs_nodes = cs_nodes[start_idx:end_idx]

    for node in cs_nodes:
        # Map chainage to j-index
        j = int(round(node.chainage / total_length * (ny - 1)))
        j = max(0, min(ny - 1, j))
        node_index = list(node_ids_in_reach).index(node.id)

        # Two interface cells: left and right of channel
        for i_bank in [i_channel - 1, i_channel + 1]:
            i_bank = max(0, min(nx - 1, i_bank))
            points.append(InterfacePoint(
                node_id=node.id,
                node_index=node_index,
                i=i_bank,
                j=j,
                bank_elevation=bank_elevation,
            ))

    return BankInterface(points=points)


# ── Diagnostics ──────────────────────────────────────────────────────────

def print_header():
    print("=" * 72)
    print("  1D+2D Coupled Simulation — Channel Overflow onto Floodplain")
    print("=" * 72)
    print(f"  Channel:          {N_CROSS_SECTIONS} CS, {CHANNEL_WIDTH:.0f}m wide, "
          f"bank-height {BANK_HEIGHT_CS:.1f}m")
    print(f"  Floodplain:       {NX}x{NY} grid ({NX*DX:.0f}x{NY*DY:.0f} m)")
    print(f"  Interface:        Bank elevation {BANK_ELEVATION_Z:.1f} m a.s.l.")
    print(f"  Upstream BC:      Discharge hydrograph (peak {UPSTREAM_Q_PEAK:.0f} m3/s)")
    print(f"  Downstream BC:    Fixed stage {DOWNSTREAM_STAGE:.1f} m a.s.l.")
    print(f"  Time step:        {DT:.1f} s x {TOTAL_STEPS} steps")
    print("=" * 72)
    print()


def print_step(state, step, t):
    s1d = state.state_1d
    s2d = state.state_2d
    exchange = state.exchange_flux

    Q_up = float(s1d.discharge[0])
    Q_mid = float(np.mean(s1d.discharge[1:-1]))
    h1d_max = float(np.max(s1d.water_surface_elev[1:-1]))

    h2d_max = float(np.max(s2d.water_depth))
    wet_2d = int(np.sum(s2d.water_depth > 0.001))

    net_exchange = float(np.sum(exchange))  # positive = channel to floodplain

    print(
        f"  step {step:>3d}  t={t:>7.1f}s  "
        f"Q_up={Q_up:>7.1f}  h1d_max={h1d_max:>5.3f}  "
        f"h2d_max={h2d_max:>5.4f}  wet2d={wet_2d:>5d}  "
        f"Q_ex_net={net_exchange:>8.3f}"
    )


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print_header()

    cfg = get_config()

    # Configure 2D grid for this example
    cfg.physics.solver_2d.nx = NX
    cfg.physics.solver_2d.ny = NY
    cfg.physics.solver_2d.dx = DX
    cfg.physics.solver_2d.dy = DY
    cfg.terrain.initial_water_depth = 0.0

    # Build components
    network = build_network()
    print(f"  Network: {len(network.nodes)} nodes, {len(network.edges)} reach(es)")

    bed = build_bed_terrain(NX, NY)
    print(f"  Terrain elevation: {bed.min():.2f} — {bed.max():.2f} m")

    interface = build_interface(network, NX, NY, BANK_ELEVATION_Z)
    print(f"  Interface: {interface.n_points} coupling points")
    print()

    # Initialize engine
    engine = SimulationEngine(mode="1d2d", config=cfg)
    engine.initialize(
        network=network,
        interface=interface,
        bed_elevation=bed,
        dx=DX,
        dy=DY,
    )
    print(f"  Engine initialized in mode '{engine.mode}'")

    # Print initial WSE range for context
    s1d_init = engine._solver_1d.state
    print(f"  Initial 1D WSE range: {s1d_init.water_surface_elev[1:-1].min():.3f} — "
          f"{s1d_init.water_surface_elev[1:-1].max():.3f} m a.s.l.")
    print(f"  Bank elevation:       {BANK_ELEVATION_Z:.1f} m a.s.l.")
    print()

    # ── Run simulation ────────────────────────────────────────────────────
    print(
        f"  {'step':>4s}  {'time':>6s}  "
        f"{'Q_up':>7s}  {'h1d_max':>7s}  "
        f"{'h2d_max':>7s}  {'wet2d':>6s}  {'Q_ex_net':>8s}"
    )
    print("  " + "-" * 68)

    start = time.perf_counter()
    overflow_steps = 0
    max_exchange = 0.0

    for step in range(TOTAL_STEPS):
        try:
            state = engine.step(dt=DT)
        except Exception as e:
            print(f"\n  Solver diverged at step {step}: {e}")
            print(f"  Stopping simulation at step {step}/{TOTAL_STEPS}")
            break

        exchange = state.exchange_flux
        if np.any(np.abs(exchange) > 1e-6):
            overflow_steps += 1
        max_exchange = max(max_exchange, float(np.max(np.abs(exchange))))

        if step % PRINT_EVERY == 0 or step == TOTAL_STEPS - 1:
            print_step(state, step, engine.current_time)

    elapsed = time.perf_counter() - start
    print("  " + "-" * 68)
    print()

    # ── Final state summary ───────────────────────────────────────────────
    state = engine.state
    s1d = state.state_1d
    s2d = state.state_2d

    print("  Final State:")
    print(f"    Elapsed time:      {engine.current_time:.1f} s")
    print(f"    1D max Q:          {s1d.max_discharge:.2f} m3/s")
    print(f"    1D max WSE:        {np.max(s1d.water_surface_elev):.4f} m a.s.l.")
    print(f"    2D max depth:      {np.max(s2d.water_depth):.4f} m")
    wet_cells = int(np.sum(s2d.water_depth > 0.001))
    print(f"    2D wet cells:      {wet_cells}")
    print(f"    Interface points:  {state.exchange_flux.shape[0]}")
    print(f"    Overflow steps:    {overflow_steps}/{TOTAL_STEPS}")
    print(f"    Max exchange flux: {max_exchange:.4f} m3/s")
    print()

    # ── Validation ────────────────────────────────────────────────────────
    print("  Validation:")
    n_pass = 0
    n_total = 0

    # 1. No NaN/Inf in 1D state
    n_total += 1
    if (np.all(np.isfinite(s1d.discharge)) and
        np.all(np.isfinite(s1d.water_surface_elev))):
        print("    [PASS] 1D state: all finite")
        n_pass += 1
    else:
        print("    [FAIL] 1D state: NaN/Inf detected")

    # 2. No NaN/Inf in 2D state
    n_total += 1
    if np.all(np.isfinite(s2d.water_depth)):
        print("    [PASS] 2D state: all finite")
        n_pass += 1
    else:
        print("    [FAIL] 2D state: NaN/Inf detected")

    # 3. Non-negative 2D depths
    n_total += 1
    if np.all(s2d.water_depth >= 0):
        print("    [PASS] 2D depths: all non-negative")
        n_pass += 1
    else:
        print(f"    [FAIL] 2D depths: negative found (min={np.min(s2d.water_depth):.6f})")

    # 4. Exchange flux is physically reasonable
    n_total += 1
    if max_exchange < 1000:  # shouldn't be extreme
        print(f"    [PASS] Exchange flux: reasonable (max={max_exchange:.4f} m3/s)")
        n_pass += 1
    else:
        print(f"    [FAIL] Exchange flux: extreme values (max={max_exchange:.1f})")

    # 5. Downstream stage enforced
    n_total += 1
    h_ds = float(s1d.water_surface_elev[-1])
    if abs(h_ds - DOWNSTREAM_STAGE) < 0.2:
        print(f"    [PASS] Downstream stage: {h_ds:.4f} ≈ {DOWNSTREAM_STAGE:.1f}")
        n_pass += 1
    else:
        print(f"    [FAIL] Downstream stage: {h_ds:.4f} vs {DOWNSTREAM_STAGE:.1f}")

    # 6. 1D velocities physical
    n_total += 1
    v_max_1d = float(np.max(np.abs(s1d.velocity[1:-1])))
    if v_max_1d < 15.0:
        print(f"    [PASS] 1D max velocity: {v_max_1d:.3f} m/s < 15 m/s")
        n_pass += 1
    else:
        print(f"    [FAIL] 1D excessive velocity: {v_max_1d:.3f} m/s")

    # 7. 2D velocities physical
    n_total += 1
    v_max_2d = float(np.sqrt(np.max(s2d.velocity_x**2 + s2d.velocity_y**2)))
    if v_max_2d < 15.0:
        print(f"    [PASS] 2D max velocity: {v_max_2d:.3f} m/s < 15 m/s")
        n_pass += 1
    else:
        print(f"    [FAIL] 2D excessive velocity: {v_max_2d:.3f} m/s")

    # Performance
    steps_completed = step + 1
    print(f"\n    [INFO] Performance: {steps_completed/elapsed:.1f} steps/s "
          f"({elapsed:.3f}s total, {steps_completed}/{TOTAL_STEPS} steps)")

    print()
    print(f"  Result: {n_pass}/{n_total} checks passed")
    print("=" * 72)


if __name__ == "__main__":
    main()
