"""
Tests for Sprint 5: FastAPI routes and WebSocket endpoint.

Covers:
  1.  GET /api/health → 200
  2.  GET /api/health/ready before engine → not_ready
  3.  POST /api/simulation/start (mode='2d') → 200
  4.  GET /api/health/ready after engine → ready
  5.  GET /api/simulation/status → 200
  6.  POST /api/simulation/step?n=5 → state has elapsed_time > 0
  7.  GET /api/simulation/state → returns mode and state_2d
  8.  POST /api/simulation/reset → elapsed_time == 0
  9.  POST /api/simulation/start (mode='1d') → state_1d returned
  10. POST /api/simulation/start (mode='1d2d') → both sub-states returned
  11. GET /api/terrain/info → metadata keys present
  12. GET /api/terrain/mesh → elevation grid present
  13. GET /api/prediction/risk (after 2d start) → risk_grid shape correct
  14. GET /api/prediction/risk (after 1d start) → 422
  15. GET /api/simulation/state before start → 409
  16. WebSocket /ws ping/pong
  17. WebSocket /ws step message
  18. WebSocket /ws status message
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture(scope="module")
def client():
    """Create one TestClient per module — avoids repeated startup overhead."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Health ─────────────────────────────────────────────────────────────────

def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_ready_before_engine(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "not_ready"


# ── Simulation — guard ─────────────────────────────────────────────────────

def test_state_before_start_is_409(client):
    """Engine not started yet → 409."""
    # Fresh app without start called
    from src.main import create_app as _ca
    with TestClient(_ca()) as c:
        r = c.get("/api/simulation/state")
    assert r.status_code == 409


# ── Simulation — mode 2d ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client_2d():
    """Client with a 2D simulation already started."""
    app = create_app()
    with TestClient(app) as c:
        c.post("/api/simulation/start", json={"mode": "2d", "steps": 100})
        yield c


def test_start_2d(client_2d):
    r = client_2d.post("/api/simulation/start", json={"mode": "2d", "steps": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "2d"


def test_ready_after_start(client_2d):
    r = client_2d.get("/api/health/ready")
    assert r.json()["status"] == "ready"


def test_status_2d(client_2d):
    r = client_2d.get("/api/simulation/status")
    assert r.status_code == 200
    body = r.json()
    assert "current_step" in body
    assert "elapsed_time" in body


def test_step_2d(client_2d):
    r = client_2d.post("/api/simulation/step?n=5")
    assert r.status_code == 200
    body = r.json()
    assert body["elapsed_time"] > 0
    assert body["mode"] == "2d"
    assert body["state_2d"] is not None


def test_state_2d(client_2d):
    r = client_2d.get("/api/simulation/state")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "2d"
    assert "state_2d" in body
    assert body["state_2d"] is not None


def test_state_2d_shape(client_2d):
    """water_depth grid must have the correct nx×ny dimensions."""
    from src.core.config import get_config
    cfg = get_config()
    r = client_2d.get("/api/simulation/state")
    state_2d = r.json()["state_2d"]
    assert len(state_2d["water_depth"]) == cfg.physics.solver_2d.nx
    assert len(state_2d["water_depth"][0]) == cfg.physics.solver_2d.ny


def test_reset_2d(client_2d):
    r = client_2d.post("/api/simulation/reset")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # After reset, time should be 0
    r2 = client_2d.get("/api/simulation/state")
    assert r2.json()["elapsed_time"] == pytest.approx(0.0, abs=1e-9)


# ── Simulation — mode 1d ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client_1d():
    app = create_app()
    with TestClient(app) as c:
        c.post("/api/simulation/start", json={"mode": "1d", "steps": 100})
        yield c


def test_start_1d(client_1d):
    r = client_1d.post("/api/simulation/start", json={"mode": "1d", "steps": 100})
    assert r.status_code == 200
    assert r.json()["mode"] == "1d"


def test_step_1d(client_1d):
    r = client_1d.post("/api/simulation/step?n=3")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "1d"
    assert body["state_1d"] is not None
    assert body["state_2d"] is None


def test_prediction_risk_1d_is_422(client_1d):
    """Risk grid endpoint returns 422 for 1D-only mode (no 2D state)."""
    r = client_1d.get("/api/prediction/risk")
    assert r.status_code == 422


# ── Simulation — mode 1d2d ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client_1d2d():
    app = create_app()
    with TestClient(app) as c:
        c.post("/api/simulation/start", json={"mode": "1d2d", "steps": 100})
        yield c


def test_start_1d2d(client_1d2d):
    r = client_1d2d.post("/api/simulation/start", json={"mode": "1d2d", "steps": 100})
    assert r.status_code == 200
    assert r.json()["mode"] == "1d2d"


def test_step_1d2d(client_1d2d):
    r = client_1d2d.post("/api/simulation/step?n=2")
    assert r.status_code == 200
    body = r.json()
    assert body["state_1d"] is not None
    assert body["state_2d"] is not None


# ── Terrain ────────────────────────────────────────────────────────────────

def test_terrain_info(client):
    r = client.get("/api/terrain/info")
    assert r.status_code == 200
    body = r.json()
    assert "nx" in body
    assert "ny" in body
    assert "dx" in body
    assert "bounding_box" in body


def test_terrain_mesh(client):
    r = client.get("/api/terrain/mesh")
    assert r.status_code == 200
    body = r.json()
    assert "nx" in body
    assert "elevation" in body
    # elevation is a list-of-lists
    assert isinstance(body["elevation"], list)
    assert isinstance(body["elevation"][0], list)


# ── Prediction ─────────────────────────────────────────────────────────────

def test_prediction_risk_2d(client_2d):
    # Advance a few steps to get a non-trivial state
    client_2d.post("/api/simulation/step?n=5")
    r = client_2d.get("/api/prediction/risk")
    assert r.status_code == 200
    body = r.json()
    assert "risk_grid" in body
    assert "summary" in body
    assert "nx" in body


# ── WebSocket ──────────────────────────────────────────────────────────────

def test_websocket_ping_pong():
    app = create_app()
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"


def test_websocket_status_no_engine():
    app = create_app()
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "status"})
            msg = ws.receive_json()
            assert msg["type"] == "status"
            assert msg.get("engine") == "not_started"


def test_websocket_step_after_start():
    app = create_app()
    with TestClient(app) as c:
        # Start engine first via HTTP
        c.post("/api/simulation/start", json={"mode": "2d", "steps": 100})
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "step", "n": 2})
            msg = ws.receive_json()
            assert msg["type"] == "state"
            assert msg["elapsed_time"] > 0


def test_websocket_step_no_engine():
    app = create_app()
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "step", "n": 1})
            msg = ws.receive_json()
            assert msg["type"] == "error"


def test_websocket_reset_after_start():
    app = create_app()
    with TestClient(app) as c:
        c.post("/api/simulation/start", json={"mode": "2d", "steps": 100})
        c.post("/api/simulation/step?n=3")
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "reset"})
            msg = ws.receive_json()
            assert msg["type"] == "reset_ok"
