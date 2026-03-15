"""
Tests for Sprint 4: 1D+2D Coupler + SimulationEngine Orchestrator.

Key test cases:
  1.  Exchange flux is zero when both sides are below the bank crest
  2.  Positive exchange when channel WSE > bank elevation
  3.  Negative exchange (return flow) when floodplain WSE > bank elevation
  4.  Weir formula magnitude matches analytic expectation
  5.  Mass is conserved through apply_exchange_to_2d
  6.  BankInterface.extract_wse_1d reads correct nodes
  7.  BankInterface.extract_wse_2d returns η = z + h
  8.  Engine mode '1d': step returns Solver1DState, time advances
  9.  Engine mode '2d': step returns Solver2DState, time advances
  10. Engine mode '1d2d': step returns CoupledState
  11. Engine reset returns time to 0
  12. Async run yields correct number of states
  13. Async run respects yield_every parameter
"""
from __future__ import annotations

import asyncio
import math

import numpy as np
import pytest

from src.physics.coupled.coupler import (
    compute_exchange,
    apply_exchange_to_2d,
    apply_exchange_to_1d_Q,
)
from src.physics.coupled.interface import BankInterface, InterfacePoint
from src.physics.engine import SimulationEngine
from src.physics.state import Solver1DState, Solver2DState, CoupledState
from src.physics.solver_1d.cross_section import CrossSection
from src.physics.solver_1d.network import ChannelNetwork


# ── Helpers ───────────────────────────────────────────────────────────────

def make_network(n_cs: int = 5, reach_length: float = 500.0, width: float = 10.0):
    cs = CrossSection.rectangular(width=width, z_bed=0.0, bank_height=6.0)
    return ChannelNetwork.simple_reach(
        n_cross_sections=n_cs,
        reach_length=reach_length,
        cross_section=cs,
        upstream_Q=30.0,
        downstream_h=3.0,
    )


def _dummy_state_1d(wse_values) -> Solver1DState:
    n = len(wse_values)
    return Solver1DState(
        chainage=np.linspace(0, 100, n),
        discharge=np.zeros(n),
        water_surface_elev=np.array(wse_values, dtype=float),
        area=np.ones(n),
        velocity=np.zeros(n),
        node_ids=[f"n{i}" for i in range(n)],
    )


def _dummy_state_2d(nx: int = 5, ny: int = 5, h: float = 0.5, z: float = 0.0) -> Solver2DState:
    return Solver2DState(
        water_depth=np.full((nx, ny), h),
        velocity_x=np.zeros((nx, ny)),
        velocity_y=np.zeros((nx, ny)),
        bed_elevation=np.full((nx, ny), z),
        rainfall_rate=np.zeros((nx, ny)),
        flood_risk=np.zeros((nx, ny), dtype=np.int8),
    )


# ── Exchange flux unit tests ───────────────────────────────────────────────

class TestComputeExchange:
    def test_no_exchange_both_below_bank(self):
        """Both sides below bank → zero flux everywhere."""
        bank_z = np.array([5.0, 5.0])
        wse_1d = np.array([2.0, 3.0])
        wse_2d = np.array([1.0, 2.0])
        ex = compute_exchange(wse_1d, wse_2d, bank_z, cell_width=10.0)
        np.testing.assert_allclose(ex, 0.0, atol=1e-10)

    def test_positive_when_channel_overflows(self):
        """Channel WSE above bank → positive overflow to floodplain."""
        bank_z = np.array([2.0])
        wse_1d = np.array([4.0])   # 2 m above bank
        wse_2d = np.array([0.5])   # well below bank
        ex = compute_exchange(wse_1d, wse_2d, bank_z, cell_width=10.0)
        assert ex[0] > 0.0

    def test_negative_when_floodplain_returns(self):
        """Floodplain WSE above bank → negative (return flow to channel)."""
        bank_z = np.array([2.0])
        wse_1d = np.array([1.0])   # below bank
        wse_2d = np.array([4.0])   # 2 m above bank
        ex = compute_exchange(wse_1d, wse_2d, bank_z, cell_width=10.0)
        assert ex[0] < 0.0

    def test_weir_formula_magnitude(self):
        """Q = Cd * L * sqrt(2g) * h^1.5 for one-sided overflow."""
        bank_z = np.array([0.0])
        h_over = 2.0
        wse_1d = np.array([h_over])
        wse_2d = np.array([-1.0])   # channel clearly higher
        Cd, L = 0.4, 10.0
        expected = Cd * L * math.sqrt(2 * 9.81) * h_over ** 1.5
        ex = compute_exchange(wse_1d, wse_2d, bank_z, cell_width=L, weir_coeff=Cd)
        assert ex[0] == pytest.approx(expected, rel=0.01)

    def test_zero_exchange_at_exact_bank_height(self):
        """WSE exactly at bank → head over bank is zero → zero flux."""
        bank_z = np.array([3.0])
        wse_1d = np.array([3.0])
        wse_2d = np.array([1.0])
        ex = compute_exchange(wse_1d, wse_2d, bank_z, cell_width=10.0)
        assert ex[0] == pytest.approx(0.0, abs=1e-12)


class TestApplyExchangeTo2D:
    def test_volume_added_equals_exchange_times_dt(self):
        """Volume gained by 2D cells = sum(Q_ex) * dt."""
        nx, ny = 5, 5
        h2d = np.zeros((nx, ny))
        exchange = np.array([5.0, 3.0])   # m³/s positive → gain
        i_arr = np.array([1, 2])
        j_arr = np.array([2, 3])
        dt, dx, dy = 10.0, 100.0, 100.0

        vol_before = float(np.sum(h2d[i_arr, j_arr]) * dx * dy)
        apply_exchange_to_2d(h2d, exchange, i_arr, j_arr, dt, dx, dy)
        vol_after = float(np.sum(h2d[i_arr, j_arr]) * dx * dy)

        expected_gain = float(np.sum(exchange) * dt)
        assert (vol_after - vol_before) == pytest.approx(expected_gain, rel=0.01)

    def test_no_negative_depth(self):
        """Large negative exchange should not produce h < 0."""
        h2d = np.zeros((3, 3))
        exchange = np.array([-1000.0])   # huge return flux
        apply_exchange_to_2d(h2d, exchange, np.array([1]), np.array([1]),
                              dt=1.0, dx=1.0, dy=1.0)
        assert np.all(h2d >= 0.0)


# ── BankInterface tests ────────────────────────────────────────────────────

class TestBankInterface:
    def test_extract_wse_1d(self):
        """Interface reads WSE at the correct node indices."""
        points = [
            InterfacePoint("n1", 1, 2, 2, bank_elevation=3.0),
            InterfacePoint("n2", 2, 2, 3, bank_elevation=3.0),
        ]
        iface = BankInterface(points=points)
        state_1d = _dummy_state_1d([1.0, 2.0, 4.0, 1.0])
        wse = iface.extract_wse_1d(state_1d)
        np.testing.assert_allclose(wse, [2.0, 4.0])

    def test_extract_wse_2d(self):
        """Interface computes η = z + h from the 2D state."""
        points = [InterfacePoint("n0", 0, 1, 2, bank_elevation=3.0)]
        iface = BankInterface(points=points)
        state_2d = _dummy_state_2d(h=0.5, z=1.0)   # η = 1.5
        wse = iface.extract_wse_2d(state_2d)
        np.testing.assert_allclose(wse, [1.5])

    def test_bank_elevations_array(self):
        """bank_elevations() returns the correct crest heights."""
        points = [
            InterfacePoint("n0", 0, 0, 0, bank_elevation=2.5),
            InterfacePoint("n1", 1, 0, 1, bank_elevation=3.0),
        ]
        iface = BankInterface(points=points)
        np.testing.assert_allclose(iface.bank_elevations(), [2.5, 3.0])

    def test_n_points(self):
        iface = BankInterface(points=[
            InterfacePoint("a", 0, 0, 0, 1.0),
            InterfacePoint("b", 1, 0, 1, 1.0),
        ])
        assert iface.n_points == 2

    def test_from_reach_builds_points(self):
        """from_reach should create one point per interior cross-section."""
        net = make_network(n_cs=4)
        iface = BankInterface.from_reach(
            network=net, reach_id="r0",
            nx=10, ny=10, dx=50.0, dy=50.0,
            bank_elevation=3.0,
        )
        # 4 interior cross-section nodes → 4 interface points
        assert iface.n_points == 4


# ── SimulationEngine — mode '1d' ──────────────────────────────────────────

class TestEngineMode1D:
    def test_step_returns_1d_state(self):
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())
        state = engine.step()
        assert isinstance(state, Solver1DState)

    def test_time_advances(self):
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())
        engine.step()
        assert engine.current_time > 0.0

    def test_no_nan_after_10_steps(self):
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())
        for _ in range(10):
            state = engine.step()
        assert np.all(np.isfinite(state.discharge))
        assert np.all(np.isfinite(state.water_surface_elev))

    def test_reset_to_zero(self):
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())
        for _ in range(5):
            engine.step()
        assert engine.current_time > 0.0
        engine.reset()
        assert engine.current_time == 0.0

    def test_state_property(self):
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())
        assert isinstance(engine.state, Solver1DState)


# ── SimulationEngine — mode '2d' ──────────────────────────────────────────

class TestEngineMode2D:
    def test_step_returns_2d_state(self):
        engine = SimulationEngine(mode="2d")
        engine.initialize()
        state = engine.step()
        assert isinstance(state, Solver2DState)

    def test_time_advances(self):
        engine = SimulationEngine(mode="2d")
        engine.initialize()
        engine.step()
        assert engine.current_time > 0.0

    def test_no_nan_after_10_steps(self):
        engine = SimulationEngine(mode="2d")
        engine.initialize()
        for _ in range(10):
            state = engine.step()
        assert np.all(np.isfinite(state.water_depth))

    def test_reset_to_zero(self):
        engine = SimulationEngine(mode="2d")
        engine.initialize()
        for _ in range(5):
            engine.step()
        assert engine.current_time > 0.0
        engine.reset()
        assert engine.current_time == 0.0

    def test_state_property(self):
        engine = SimulationEngine(mode="2d")
        engine.initialize()
        assert isinstance(engine.state, Solver2DState)


# ── SimulationEngine — mode '1d2d' ────────────────────────────────────────

class TestEngineMode1D2D:
    def test_step_returns_coupled_state(self):
        engine = SimulationEngine(mode="1d2d")
        engine.initialize(network=make_network())
        state = engine.step()
        assert isinstance(state, CoupledState)
        assert isinstance(state.state_1d, Solver1DState)
        assert isinstance(state.state_2d, Solver2DState)

    def test_time_advances(self):
        engine = SimulationEngine(mode="1d2d")
        engine.initialize(network=make_network())
        engine.step()
        assert engine.current_time > 0.0

    def test_no_nan_after_10_steps(self):
        engine = SimulationEngine(mode="1d2d")
        engine.initialize(network=make_network())
        for _ in range(10):
            state = engine.step()
        assert np.all(np.isfinite(state.state_1d.discharge))
        assert np.all(np.isfinite(state.state_2d.water_depth))

    def test_exchange_flux_is_array(self):
        """exchange_flux is a numpy array (may be empty with trivial interface)."""
        engine = SimulationEngine(mode="1d2d")
        engine.initialize(network=make_network())
        state = engine.step()
        assert isinstance(state.exchange_flux, np.ndarray)

    def test_reset_to_zero(self):
        engine = SimulationEngine(mode="1d2d")
        engine.initialize(network=make_network())
        for _ in range(5):
            engine.step()
        assert engine.current_time > 0.0
        engine.reset()
        assert engine.current_time == 0.0

    def test_state_property_coupled(self):
        engine = SimulationEngine(mode="1d2d")
        engine.initialize(network=make_network())
        assert isinstance(engine.state, CoupledState)

    def test_with_active_interface(self):
        """Coupled engine with a real interface: no NaNs and exchange is finite."""
        net = make_network(n_cs=4)
        from src.core.config import get_config
        cfg = get_config()
        iface = BankInterface.from_reach(
            network=net, reach_id="r0",
            nx=cfg.physics.solver_2d.nx,
            ny=cfg.physics.solver_2d.ny,
            dx=cfg.physics.solver_2d.dx,
            dy=cfg.physics.solver_2d.dy,
            bank_elevation=3.5,
        )
        engine = SimulationEngine(mode="1d2d", config=cfg)
        engine.initialize(network=net, interface=iface)
        for _ in range(5):
            state = engine.step()
        assert np.all(np.isfinite(state.exchange_flux))
        assert np.all(np.isfinite(state.state_1d.discharge))
        assert np.all(np.isfinite(state.state_2d.water_depth))


# ── Async interface tests ─────────────────────────────────────────────────

class TestEngineAsync:
    def test_run_yields_all_steps(self):
        """run(steps=5, yield_every=1) should yield exactly 5 states."""
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())

        async def collect():
            results = []
            async for state in engine.run(steps=5, yield_every=1):
                results.append(state)
            return results

        results = asyncio.run(collect())
        assert len(results) == 5

    def test_run_respects_yield_every(self):
        """run(steps=6, yield_every=2) should yield 3 states."""
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())

        async def collect():
            results = []
            async for state in engine.run(steps=6, yield_every=2):
                results.append(state)
            return results

        results = asyncio.run(collect())
        assert len(results) == 3

    def test_run_time_progresses(self):
        """After async run, engine time should be > 0."""
        engine = SimulationEngine(mode="1d")
        engine.initialize(network=make_network())

        async def go():
            async for _ in engine.run(steps=3):
                pass

        asyncio.run(go())
        assert engine.current_time > 0.0
