"""
Tests for Sprint 3: 1D Preissmann Solver + Channel Network.

Key test cases:
  1. CrossSection geometry: A, P, T computed correctly for rectangular channel
  2. Network construction: nodes, edges, boundary conditions
  3. Solver initializes without error
  4. Solver advances time
  5. Mass conservation along a single reach
  6. Solver is stable at dt=10s on 20-node network
  7. Boundary conditions enforced at each step
"""
from __future__ import annotations

import math
import numpy as np
import pytest

from src.physics.solver_1d.cross_section import CrossSection
from src.physics.solver_1d.network import (
    ChannelNetwork, NetworkNode, NetworkEdge,
    NodeType, BoundaryCondition1D, BCType1D,
)
from src.physics.solver_1d.preissmann import Solver1D


# ── CrossSection tests ────────────────────────────────────────────────────

class TestCrossSection:
    def test_rectangular_area(self):
        """Rectangular channel: A = width * depth."""
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        # At h_ws = 2.0m above bed (z_bed=0), depth = 2.0m
        A = cs.area(2.0)
        assert A == pytest.approx(10.0 * 2.0, rel=0.02)

    def test_rectangular_perimeter(self):
        """Rectangular channel: P ≈ width + 2*depth (steep-wall approximation)."""
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        P = cs.perimeter(2.0)
        # Steep walls add a tiny extra to the perimeter vs true vertical walls.
        # Allow 10% rel tolerance for the approximation.
        assert P == pytest.approx(10.0 + 2 * 2.0, rel=0.10)

    def test_rectangular_top_width(self):
        """Rectangular channel: T = width (constant)."""
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        T = cs.top_width(2.0)
        assert T == pytest.approx(10.0, rel=0.02)

    def test_hydraulic_radius(self):
        """R = A / P for rectangular channel."""
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        h_ws = 2.0
        A = cs.area(h_ws)
        P = cs.perimeter(h_ws)
        R = cs.hydraulic_radius(h_ws)
        assert R == pytest.approx(A / P, rel=0.02)

    def test_dry_section(self):
        """Below bed elevation: all geometry = 0."""
        cs = CrossSection.rectangular(width=10.0, z_bed=5.0, bank_height=3.0)
        assert cs.area(4.0) == pytest.approx(0.0, abs=1e-6)
        assert cs.perimeter(4.0) == pytest.approx(0.0, abs=1e-6)

    def test_area_monotone_increasing(self):
        """Area must be non-decreasing with water level."""
        cs = CrossSection.trapezoidal(bottom_width=8.0, side_slope=1.5,
                                       z_bed=0.0, bank_height=4.0)
        h_levels = np.linspace(0.1, 4.0, 20)
        areas = np.array([cs.area(h) for h in h_levels])
        assert np.all(np.diff(areas) >= 0), "Area must be non-decreasing"

    def test_h_from_area_roundtrip(self):
        """h_from_area(area(h)) ≈ h."""
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        for h_ws in [0.5, 1.0, 2.5, 4.0]:
            A = cs.area(h_ws)
            h_recovered = cs.h_from_area(A)
            assert h_recovered == pytest.approx(h_ws, abs=0.05)

    def test_vectorized_lookup(self):
        """Area lookup accepts numpy array input."""
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        h_arr = np.array([1.0, 2.0, 3.0])
        A_arr = cs.area(h_arr)
        assert A_arr.shape == (3,)
        np.testing.assert_allclose(A_arr, [10.0, 20.0, 30.0], rtol=0.02)


# ── Network tests ─────────────────────────────────────────────────────────

class TestChannelNetwork:
    def test_simple_reach_creation(self):
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0, bank_height=5.0)
        net = ChannelNetwork.simple_reach(
            n_cross_sections=10,
            reach_length=1000.0,
            cross_section=cs,
            upstream_Q=30.0,
            downstream_h=3.0,
        )
        assert len(net.nodes) == 12   # 10 cs + 2 boundaries
        assert len(net.edges) == 1

    def test_boundary_nodes_exist(self):
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0)
        net = ChannelNetwork.simple_reach(5, 500.0, cs)
        boundaries = net.boundary_nodes()
        assert len(boundaries) == 2

    def test_upstream_bc_type(self):
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0)
        net = ChannelNetwork.simple_reach(5, 500.0, cs, upstream_Q=50.0)
        up_node = net.get_node("upstream")
        assert up_node.boundary_condition.bc_type == BCType1D.DISCHARGE
        assert up_node.boundary_condition.get_value(0) == pytest.approx(50.0)

    def test_downstream_bc_type(self):
        cs = CrossSection.rectangular(width=10.0, z_bed=0.0)
        net = ChannelNetwork.simple_reach(5, 500.0, cs, downstream_h=4.0)
        down_node = net.get_node("downstream")
        assert down_node.boundary_condition.bc_type == BCType1D.STAGE
        assert down_node.boundary_condition.get_value(0) == pytest.approx(4.0)

    def test_bc_interpolation(self):
        """Time-varying BC should interpolate correctly."""
        bc = BoundaryCondition1D(
            bc_type=BCType1D.DISCHARGE,
            times=np.array([0.0, 100.0, 200.0]),
            values=np.array([10.0, 50.0, 20.0]),
        )
        assert bc.get_value(50.0) == pytest.approx(30.0, rel=0.01)
        assert bc.get_value(150.0) == pytest.approx(35.0, rel=0.01)


# ── Solver tests ──────────────────────────────────────────────────────────

def make_solver(n_cs=10, reach_length=1000.0, width=10.0, upstream_Q=30.0,
                downstream_h=3.0, slope=0.001) -> Solver1D:
    cs = CrossSection.rectangular(width=width, z_bed=0.0, bank_height=8.0)
    net = ChannelNetwork.simple_reach(
        n_cross_sections=n_cs,
        reach_length=reach_length,
        cross_section=cs,
        slope=slope,
        upstream_Q=upstream_Q,
        downstream_h=downstream_h,
    )
    return Solver1D(network=net)


class TestSolver1DBasic:
    def test_initialize_no_error(self):
        solver = make_solver()
        solver.initialize()
        assert solver.current_time == 0.0

    def test_step_advances_time(self):
        solver = make_solver()
        solver.initialize()
        solver.step()
        assert solver.current_time > 0.0

    def test_state_arrays_shape(self):
        solver = make_solver(n_cs=10)
        solver.initialize()
        solver.step()
        state = solver.state
        # 10 interior cs + 2 boundary nodes = 12 total
        n = 12
        assert state.discharge.shape == (n,)
        assert state.water_surface_elev.shape == (n,)
        assert len(state.node_ids) == n

    def test_no_nan_after_steps(self):
        solver = make_solver()
        solver.initialize()
        for _ in range(20):
            solver.step()
        state = solver.state
        assert np.all(np.isfinite(state.discharge))
        assert np.all(np.isfinite(state.water_surface_elev))

    def test_downstream_stage_enforced(self):
        """Downstream water surface must match BC stage."""
        solver = make_solver(downstream_h=3.5)
        solver.initialize()
        for _ in range(10):
            solver.step()
        h_ds = solver.state.water_surface_elev[-1]
        assert h_ds == pytest.approx(3.5, abs=0.1)

    def test_upstream_discharge_enforced(self):
        """Upstream discharge must match BC value."""
        solver = make_solver(upstream_Q=25.0)
        solver.initialize()
        for _ in range(10):
            solver.step()
        Q_us = solver.state.discharge[0]
        assert Q_us == pytest.approx(25.0, abs=1.0)


class TestSolver1DStability:
    def test_stable_at_large_dt(self):
        """Implicit scheme must remain stable at dt=10s (explicit would blow up)."""
        solver = make_solver(n_cs=20, reach_length=2000.0)
        solver.initialize()
        for _ in range(100):
            solver.step(dt=10.0)
        state = solver.state
        assert np.all(np.isfinite(state.discharge))
        assert np.all(np.isfinite(state.water_surface_elev))

    def test_physically_reasonable_velocities(self):
        """Interior cross-section velocities should be in plausible range (< 10 m/s)."""
        solver = make_solver(upstream_Q=50.0)
        solver.initialize()
        for _ in range(50):
            solver.step()
        state = solver.state
        # Exclude boundary nodes (index 0 and -1): they have placeholder area=1 m²
        v_interior = state.velocity[1:-1]
        max_v = np.max(np.abs(v_interior))
        assert max_v < 10.0, f"Unrealistic interior velocity: {max_v:.2f} m/s"


class TestSolver1DMassConservation:
    def test_steady_state_discharge_uniform(self):
        """
        In steady state on a uniform channel with no lateral inflow,
        discharge should be nearly uniform along the reach.
        """
        solver = make_solver(n_cs=15, upstream_Q=40.0, downstream_h=4.0)
        solver.initialize()
        # Run until approximately steady state
        for _ in range(200):
            solver.step()
        state = solver.state
        # Exclude boundary nodes (indices 0 and -1)
        Q_interior = state.discharge[1:-1]
        Q_mean = np.mean(Q_interior)
        Q_var = np.std(Q_interior) / max(abs(Q_mean), 1e-9)
        assert Q_var < 0.05, f"Non-uniform discharge in steady state: CV={Q_var:.3f}"


class TestSolver1DReset:
    def test_reset_returns_to_init(self):
        solver = make_solver()
        solver.initialize()
        h0 = solver.state.water_surface_elev.copy()

        for _ in range(30):
            solver.step()
        assert solver.current_time > 0

        solver.reset()
        assert solver.current_time == 0.0
        h_after = solver.state.water_surface_elev
        np.testing.assert_allclose(h_after, h0, rtol=0.01)
