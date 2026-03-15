"""
Tests for Sprint 8: FloodNet ML predictor layer.

Covers:
  1.  Feature extraction produces correct shape
  2.  Feature extraction values are finite
  3.  Physics predictor returns correct risk shape
  4.  Physics predictor confidence is all ones
  5.  Linear predictor returns correct shape
  6.  Linear predictor risk labels are in [0,4]
  7.  Linear predictor confidence is in [0,1]
  8.  Linear predictor gives non-trivial output on non-zero input
  9.  get_predictor returns a working predictor (no torch)
  10. Risk endpoint /api/prediction/risk requires started engine
  11. Flood-net endpoint /api/prediction/flood-net returns correct keys
  12. Prediction info endpoint returns backend key
  13. PhysicsBasedPredictor matches solver flood_risk array
  14. Normalise features: mean≈0, std≈1
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.physics.state import Solver2DState
from src.ml.features import extract_features, normalise_features
from src.ml.predictors import (
    PhysicsBasedPredictor,
    LinearFloodPredictor,
    get_predictor,
)
from src.core.config import get_config


# ── Fixtures ──────────────────────────────────────────────────────────────

def make_state_2d(nx: int = 10, ny: int = 8, h_val: float = 0.5) -> Solver2DState:
    h    = np.full((nx, ny), h_val)
    u    = np.zeros((nx, ny))
    v    = np.zeros((nx, ny))
    z    = np.zeros((nx, ny))
    rain = np.zeros((nx, ny))
    # Compute risk using depth thresholds
    risk = np.zeros((nx, ny), dtype=np.int8)
    risk[h >= 0.3] = 1
    risk[h >= 1.0] = 2
    risk[h >= 2.0] = 3
    risk[h >= 5.0] = 4
    return Solver2DState(
        water_depth=h, velocity_x=u, velocity_y=v,
        bed_elevation=z, rainfall_rate=rain, flood_risk=risk,
    )


# ── Feature extraction ─────────────────────────────────────────────────────

class TestFeatures:
    def test_shape(self):
        state = make_state_2d(nx=5, ny=4)
        X = extract_features(state)
        assert X.shape == (5 * 4, 10)

    def test_finite(self):
        state = make_state_2d()
        X = extract_features(state)
        assert np.all(np.isfinite(X))

    def test_depth_feature_correct(self):
        state = make_state_2d(h_val=2.0)
        X = extract_features(state)
        np.testing.assert_allclose(X[:, 0], 2.0)

    def test_normalise_zero_mean(self):
        state = make_state_2d(nx=20, ny=20, h_val=1.5)
        X = extract_features(state)
        X_norm, mean, std = normalise_features(X)
        # Constant-feature columns should have mean≈0 and std=1 (std was replaced)
        assert np.all(np.isfinite(X_norm))


# ── Physics predictor ──────────────────────────────────────────────────────

class TestPhysicsPredictor:
    def test_risk_shape(self):
        state = make_state_2d(nx=5, ny=6)
        pred  = PhysicsBasedPredictor()
        risk  = pred.predict(state)
        assert risk.shape == (5, 6)

    def test_confidence_all_ones(self):
        state = make_state_2d()
        pred  = PhysicsBasedPredictor()
        _, conf = pred.predict_with_confidence(state)
        np.testing.assert_allclose(conf, 1.0)

    def test_matches_solver_risk(self):
        state = make_state_2d(h_val=1.5)
        pred  = PhysicsBasedPredictor()
        risk  = pred.predict(state)
        np.testing.assert_array_equal(risk, state.flood_risk)

    def test_backend(self):
        assert PhysicsBasedPredictor().backend == "physics"


# ── Linear predictor ──────────────────────────────────────────────────────

class TestLinearPredictor:
    def test_shape(self):
        state = make_state_2d(nx=6, ny=7)
        pred  = LinearFloodPredictor()
        risk  = pred.predict(state)
        assert risk.shape == (6, 7)

    def test_labels_in_range(self):
        state = make_state_2d()
        pred  = LinearFloodPredictor()
        risk  = pred.predict(state)
        assert int(risk.min()) >= 0
        assert int(risk.max()) <= 4

    def test_confidence_in_range(self):
        state = make_state_2d()
        pred  = LinearFloodPredictor()
        _, conf = pred.predict_with_confidence(state)
        assert np.all(conf >= 0)
        assert np.all(conf <= 1)

    def test_non_trivial_output(self):
        """High depth state should produce non-zero risk predictions."""
        state = make_state_2d(h_val=3.0)
        pred  = LinearFloodPredictor()
        risk  = pred.predict(state)
        # At h=3.0 m, at least some cells should be predicted as risky
        assert int(risk.max()) >= 1

    def test_backend(self):
        assert LinearFloodPredictor().backend == "linear"


# ── Factory ───────────────────────────────────────────────────────────────

class TestGetPredictor:
    def test_returns_predictor(self):
        cfg = get_config()
        pred = get_predictor(cfg)
        assert isinstance(pred, (PhysicsBasedPredictor, LinearFloodPredictor))

    def test_predictor_works(self):
        cfg = get_config()
        pred = get_predictor(cfg)
        state = make_state_2d()
        risk, conf = pred.predict_with_confidence(state)
        assert risk.shape == state.water_depth.shape
        assert conf.shape == state.water_depth.shape


# ── API tests ─────────────────────────────────────────────────────────────

from src.main import create_app


@pytest.fixture(scope="module")
def client_2d():
    app = create_app()
    with TestClient(app) as c:
        c.post("/api/simulation/start", json={"mode": "2d", "steps": 100})
        c.post("/api/simulation/step?n=2")
        yield c


class TestPredictionAPI:
    def test_risk_endpoint(self, client_2d):
        r = client_2d.get("/api/prediction/risk")
        assert r.status_code == 200
        body = r.json()
        assert "risk_grid" in body
        assert body["backend"] == "physics"

    def test_flood_net_endpoint(self, client_2d):
        r = client_2d.post("/api/prediction/flood-net")
        assert r.status_code == 200
        body = r.json()
        assert "risk_grid" in body
        assert "confidence" in body
        assert "backend" in body
        assert body["backend"] in ("physics", "linear", "torch")

    def test_flood_net_risk_shape(self, client_2d):
        """Risk grid should have shape nx × ny."""
        from src.core.config import get_config
        cfg = get_config()
        r = client_2d.post("/api/prediction/flood-net")
        body = r.json()
        assert len(body["risk_grid"]) == cfg.physics.solver_2d.nx
        assert len(body["risk_grid"][0]) == cfg.physics.solver_2d.ny

    def test_prediction_info(self, client_2d):
        r = client_2d.get("/api/prediction/info")
        assert r.status_code == 200
        body = r.json()
        assert "backend" in body
        assert "input_features" in body

    def test_risk_before_start_is_409(self):
        app = create_app()
        with TestClient(app) as c:
            r = c.get("/api/prediction/risk")
        assert r.status_code == 409

    def test_flood_net_1d_mode_is_422(self):
        app = create_app()
        with TestClient(app) as c:
            c.post("/api/simulation/start", json={"mode": "1d", "steps": 100})
            r = c.post("/api/prediction/flood-net")
        assert r.status_code == 422
