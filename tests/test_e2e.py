#!/usr/bin/env python3
"""
End-to-End Integration Tests for all solver modes.

These tests construct complete simulation scenarios (1D, 2D, 1D+2D),
run them to completion, and validate physical consistency.

Each test follows the same pattern:
  1. Build geometry (network, terrain, interface)
  2. Initialize SimulationEngine
  3. Run N steps
  4. Validate state variables (no NaN, physical bounds, BC enforcement)

Run:
  pytest tests/test_e2e.py -v
"""
from __future__ import annotations

import numpy as np
import pytest

from src.core.config import get_config
from src.physics.engine import SimulationEngine
from src.physics.coupled.interface import BankInterface, InterfacePoint
from src.physics.solver_1d.cross_section import CrossSection
from src.physics.solver_1d.network import (
    ChannelNetwork,
    BoundaryCondition1D,
    BCType1D,
)
from src.physics.solver_2d.boundary import BoundaryConditions, BCType


# ── Helpers ────────────────────────────────────────────────────────────────

def _hydrograph(base_q, peak_q, peak_time, duration):
    """Triangular flood wave."""
    times = np.array([0.0, peak_time * 0.4, peak_time,
                      peak_time + (duration - peak_time) * 0.5,
                      duration, duration + 100.0])
    values = np.array([
        base_q, base_q + 0.4 * (peak_q - base_q), peak_q,
        base_q + 0.3 * (peak_q - base_q), base_q, base_q,
    ])
    return BoundaryCondition1D(BCType1D.DISCHARGE, times, values)


def _make_network(n_cs=12, reach_length=2000.0, width=10.0,
                  slope=0.001, upstream_Q=5.0, downstream_h=2.0):
    cs = CrossSection.rectangular(width=width, z_bed=0.0,
                                   bank_height=4.0, manning_n=0.025)
    net = ChannelNetwork.simple_reach(
        n_cross_sections=n_cs,
        reach_length=reach_length,
        cross_section=cs,
        slope=slope,
        upstream_Q=upstream_Q,
        downstream_h=downstream_h,
    )
    return net


def _make_bed_terrain(nx, ny):
    """Synthetic valley with N-S channel through center."""
    x = np.linspace(-1.0, 1.0, nx)
    y = np.linspace(-1.0, 1.0, ny)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    r = np.sqrt(xx ** 2 + yy ** 2)
    z = 10.0 * np.clip(r / 0.9, 0.0, 1.0) ** 2
    z -= 3.0 * np.exp(-(xx / 0.06) ** 2)
    z -= 0.5 * (yy + 1.0)
    rng = np.random.default_rng(42)
    z += 0.2 * rng.standard_normal((nx, ny))
    return np.maximum(z, 0.0)


def _make_interface(network, nx, ny, bank_elev):
    """Map 1D cross-section nodes to 2D cells on both bank sides."""
    reach_nodes = network.get_reach_nodes("r0")
    node_ids = network.edges["r0"].node_ids
    cs_nodes = [n for n in reach_nodes if n.cross_section is not None]
    total_length = reach_nodes[-1].chainage
    if total_length <= 0 or not cs_nodes:
        return BankInterface(points=[])

    i_ch = nx // 2
    points = []
    n_cs = len(cs_nodes)
    for node in cs_nodes[n_cs // 4: 3 * n_cs // 4]:
        j = int(round(node.chainage / total_length * (ny - 1)))
        j = max(0, min(ny - 1, j))
        nidx = list(node_ids).index(node.id)
        for ib in [i_ch - 1, i_ch + 1]:
            ib = max(0, min(nx - 1, ib))
            points.append(InterfacePoint(
                node_id=node.id, node_index=nidx,
                i=ib, j=j, bank_elevation=bank_elev))
    return BankInterface(points=points)


# ── E2E Test: 1D ──────────────────────────────────────────────────────────

class TestE2E1D:
    """End-to-end test for 1D Preissmann solver."""

    @pytest.fixture
    def engine(self):
        cfg = get_config()
        net = _make_network(n_cs=15, reach_length=3000.0, upstream_Q=10.0,
                             downstream_h=2.5)
        up_node = net.get_node("upstream")
        up_node.boundary_condition = _hydrograph(
            base_q=10.0, peak_q=60.0, peak_time=100.0, duration=250.0)
        eng = SimulationEngine(mode="1d", config=cfg)
        eng.initialize(network=net)
        return eng

    def test_runs_to_completion(self, engine):
        for _ in range(50):
            state = engine.step(dt=5.0)
        assert engine.current_time > 0

    def test_no_nan_in_state(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        state = engine.state
        assert np.all(np.isfinite(state.discharge))
        assert np.all(np.isfinite(state.water_surface_elev))
        assert np.all(np.isfinite(state.velocity))

    def test_downstream_stage_enforced(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        h_ds = engine.state.water_surface_elev[-1]
        assert abs(h_ds - 2.5) < 0.15

    def test_positive_discharge(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        assert np.all(engine.state.discharge > -0.1)

    def test_velocity_physical(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        v = engine.state.velocity[1:-1]
        assert np.max(np.abs(v)) < 15.0


# ── E2E Test: 2D ──────────────────────────────────────────────────────────

class TestE2E2D:
    """End-to-end test for 2D FV+HLLE solver."""

    @pytest.fixture
    def engine(self):
        cfg = get_config()
        cfg.physics.solver_2d.nx = 40
        cfg.physics.solver_2d.ny = 40
        cfg.physics.solver_2d.dx = 100.0
        cfg.physics.solver_2d.dy = 100.0
        cfg.terrain.amplitude = 2.0
        cfg.terrain.initial_water_depth = 0.0

        bed = _make_bed_terrain(40, 40)
        bc = BoundaryConditions(
            west=BCType.OPEN, east=BCType.OPEN,
            south=BCType.OPEN, north=BCType.OPEN)

        eng = SimulationEngine(mode="2d", config=cfg)
        eng.initialize(bed_elevation=bed, dx=100.0, dy=100.0)
        eng._solver_2d.bc = bc

        # Apply rainfall
        s = eng._solver_2d
        s._rain[:] = 0.0
        nx, ny = 40, 40
        cx, cy = 2000.0, 2000.0
        x = (np.arange(nx) + 0.5) * 100.0
        y = (np.arange(ny) + 0.5) * 100.0
        xx, yy = np.meshgrid(x, y, indexing="ij")
        r2 = (xx - cx) ** 2 + (yy - cy) ** 2
        s._rain[:] = 5e-5 * np.exp(-r2 / (2.0 * 1500.0 ** 2))

        return eng

    def test_runs_to_completion(self, engine):
        for _ in range(60):
            engine.step()
        assert engine.current_time > 0

    def test_no_nan(self, engine):
        for _ in range(60):
            engine.step()
        assert np.all(np.isfinite(engine.state.water_depth))

    def test_no_negative_depth(self, engine):
        for _ in range(60):
            engine.step()
        assert np.all(engine.state.water_depth >= 0)

    def test_rainfall_produces_flooding(self, engine):
        for _ in range(60):
            engine.step()
        wet = np.sum(engine.state.water_depth > engine._solver_2d.min_depth)
        assert wet > 0, "Rainfall should produce some flooding"

    def test_mass_conservation(self, engine):
        for _ in range(60):
            engine.step()
        err = engine._solver_2d.mass_conservation_error()
        assert err < 0.15, f"Mass conservation error too high: {err:.4f}"

    def test_velocity_physical(self, engine):
        for _ in range(60):
            engine.step()
        s = engine.state
        speed = np.sqrt(s.velocity_x ** 2 + s.velocity_y ** 2)
        assert np.max(speed) < 15.0


# ── E2E Test: 1D+2D Coupled ────────────────────────────────────────────────

class TestE2E1D2D:
    """End-to-end test for 1D+2D coupled simulation."""

    @pytest.fixture
    def engine(self):
        cfg = get_config()
        cfg.physics.solver_2d.nx = 40
        cfg.physics.solver_2d.ny = 40
        cfg.physics.solver_2d.dx = 100.0
        cfg.physics.solver_2d.dy = 100.0
        cfg.terrain.initial_water_depth = 0.0

        net = _make_network(n_cs=12, reach_length=2000.0, upstream_Q=5.0,
                             downstream_h=2.0)
        up_node = net.get_node("upstream")
        up_node.boundary_condition = _hydrograph(
            base_q=5.0, peak_q=80.0, peak_time=100.0, duration=250.0)

        bed = _make_bed_terrain(40, 40)
        interface = _make_interface(net, 40, 40, bank_elev=4.3)

        eng = SimulationEngine(mode="1d2d", config=cfg)
        eng.initialize(
            network=net, interface=interface,
            bed_elevation=bed, dx=100.0, dy=100.0)
        return eng

    def test_runs_to_completion(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        assert engine.current_time > 0

    def test_1d_state_finite(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        s = engine.state.state_1d
        assert np.all(np.isfinite(s.discharge))
        assert np.all(np.isfinite(s.water_surface_elev))

    def test_2d_state_finite(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        assert np.all(np.isfinite(engine.state.state_2d.water_depth))

    def test_no_negative_2d_depth(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        assert np.all(engine.state.state_2d.water_depth >= 0)

    def test_downstream_stage_enforced(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        h_ds = engine.state.state_1d.water_surface_elev[-1]
        assert abs(h_ds - 2.0) < 0.2

    def test_exchange_reasonable(self, engine):
        for _ in range(50):
            engine.step(dt=5.0)
        exchange = engine.state.exchange_flux
        assert np.max(np.abs(exchange)) < 500.0, \
            f"Exchange flux too large: {np.max(np.abs(exchange)):.1f}"
