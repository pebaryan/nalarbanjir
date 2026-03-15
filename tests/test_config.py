"""Tests for Sprint 1: config loading, interfaces, and schemas."""
from __future__ import annotations

import pytest
from pathlib import Path
from pydantic import ValidationError


# ── Config tests ──────────────────────────────────────────────────────────

def test_config_loads_from_yaml():
    from src.core.config import load_config
    cfg = load_config()
    assert cfg.app.name == "nalarbanjir"
    assert cfg.app.version == "2.0.0"


def test_config_physics_defaults():
    from src.core.config import load_config
    cfg = load_config()
    assert cfg.physics.gravity == pytest.approx(9.81)
    assert cfg.physics.default_mode == "2d"
    assert cfg.physics.solver_2d.nx == 100
    assert cfg.physics.solver_2d.ny == 100
    assert cfg.physics.solver_2d.cfl == pytest.approx(0.9)


def test_config_solver_1d():
    from src.core.config import load_config
    cfg = load_config()
    assert 0.5 <= cfg.physics.solver_1d.theta <= 1.0
    assert cfg.physics.solver_1d.dt > 0


def test_config_coupling():
    from src.core.config import load_config
    cfg = load_config()
    assert cfg.physics.coupling.weir_coefficient > 0


def test_config_terrain_thresholds():
    from src.core.config import load_config
    cfg = load_config()
    t = cfg.terrain.flood_thresholds
    assert t.minor < t.moderate < t.major < t.severe


def test_config_ml():
    from src.core.config import load_config
    cfg = load_config()
    assert cfg.ml.architecture.input_features == 10
    assert len(cfg.ml.architecture.hidden_dims) == 3
    assert cfg.ml.inference.mc_dropout_passes == 50


def test_config_get_config_cached():
    from src.core.config import get_config, load_config
    cfg1 = load_config()
    cfg2 = get_config()
    assert cfg1 is cfg2  # same object — cached


def test_config_invalid_cfl_raises():
    from src.core.config import Solver2DConfig
    with pytest.raises(ValidationError):
        Solver2DConfig(cfl=1.5)  # > 1.0 not allowed


def test_config_invalid_mode_raises():
    from src.core.config import PhysicsConfig
    with pytest.raises(ValidationError):
        PhysicsConfig(default_mode="3d")  # not in Literal


# ── Exception tests ───────────────────────────────────────────────────────

def test_solver_diverged_error():
    from src.core.exceptions import SolverDivergedError, NalarbanjirError
    err = SolverDivergedError("Solver2D", step=42, reason="NaN in velocity")
    assert isinstance(err, NalarbanjirError)
    assert "42" in str(err)
    assert err.solver == "Solver2D"
    assert err.step == 42


def test_gis_import_error():
    from src.core.exceptions import GISImportError
    err = GISImportError("terrain.tif", "File not found")
    assert "terrain.tif" in str(err)
    assert err.path == "terrain.tif"


def test_invalid_config_error():
    from src.core.exceptions import InvalidConfigError
    err = InvalidConfigError("cfl", 1.5, "Must be <= 1.0")
    assert "cfl" in str(err)


# ── State dataclass tests ─────────────────────────────────────────────────

def test_solver2d_state_properties():
    import numpy as np
    from src.physics.state import Solver2DState

    h = np.ones((10, 10)) * 2.0
    u = np.zeros((10, 10))
    v = np.zeros((10, 10))
    z = np.zeros((10, 10))
    rain = np.zeros((10, 10))
    risk = np.zeros((10, 10), dtype=np.int8)

    state = Solver2DState(h, u, v, z, rain, risk)
    assert state.nx == 10
    assert state.ny == 10
    assert np.allclose(state.water_surface_elevation, 2.0)
    assert np.allclose(state.speed, 0.0)
    assert state.total_volume == pytest.approx(200.0)


def test_solver1d_state_properties():
    import numpy as np
    from src.physics.state import Solver1DState

    n = 20
    state = Solver1DState(
        chainage=np.linspace(0, 1000, n),
        discharge=np.ones(n) * 50.0,
        water_surface_elev=np.linspace(10, 5, n),
        area=np.ones(n) * 25.0,
        velocity=np.ones(n) * 2.0,
        node_ids=[f"n{i}" for i in range(n)],
    )
    assert state.n_nodes == 20
    assert state.max_discharge == pytest.approx(50.0)


def test_coupled_state():
    import numpy as np
    from src.physics.state import Solver1DState, Solver2DState, CoupledState

    s1d = Solver1DState(
        chainage=np.array([0.0, 500.0]),
        discharge=np.array([30.0, 28.0]),
        water_surface_elev=np.array([5.0, 4.5]),
        area=np.array([15.0, 14.0]),
        velocity=np.array([2.0, 2.0]),
    )
    h = np.ones((5, 5))
    s2d = Solver2DState(h, np.zeros((5, 5)), np.zeros((5, 5)),
                        np.zeros((5, 5)), np.zeros((5, 5)), np.zeros((5, 5), dtype=np.int8))
    exchange = np.array([0.5, -0.2, 0.1])
    cs = CoupledState(s1d, s2d, exchange)
    assert cs.total_exchange_volume == pytest.approx(0.4)


# ── Schema tests ──────────────────────────────────────────────────────────

def test_run_request_defaults():
    from src.api.schemas.simulation import RunRequest
    req = RunRequest()
    assert req.mode == "2d"
    assert req.steps == 1000
    assert req.rainfall.intensity == 0.0


def test_run_request_validation():
    from src.api.schemas.simulation import RunRequest
    with pytest.raises(ValidationError):
        RunRequest(steps=0)   # gt=0 violated
    with pytest.raises(ValidationError):
        RunRequest(mode="3d")  # not in Literal


def test_network_schema_cross_section():
    from src.api.schemas.network import CrossSectionModel, SurveyPoint
    cs = CrossSectionModel(
        id="cs_001",
        reach_id="r1",
        chainage=500.0,
        survey_points=[
            SurveyPoint(y=0.0, z=10.0),
            SurveyPoint(y=10.0, z=8.0),
            SurveyPoint(y=20.0, z=10.0),
        ],
        bank_left_z=10.0,
        bank_right_z=10.0,
    )
    assert cs.manning_n == pytest.approx(0.03)


def test_network_schema_requires_3_points():
    from src.api.schemas.network import CrossSectionModel, SurveyPoint
    with pytest.raises(ValidationError):
        CrossSectionModel(
            id="cs_bad",
            reach_id="r1",
            chainage=0.0,
            survey_points=[SurveyPoint(y=0, z=0), SurveyPoint(y=1, z=0)],  # only 2
            bank_left_z=0.0,
            bank_right_z=0.0,
        )


def test_prediction_schema():
    from src.api.schemas.prediction import PredictRequest, RiskCell
    req = PredictRequest()
    assert req.use_current_state is True
    assert req.steps_ahead == 0

    cell = RiskCell(risk_level="major", confidence=0.85, predicted_depth=2.5, depth_uncertainty=0.3)
    assert cell.risk_level == "major"
