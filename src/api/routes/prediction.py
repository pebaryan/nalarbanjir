"""
Flood risk prediction endpoints.

GET  /api/prediction/risk             — physics-based risk grid (2D, fast, no ML)
GET  /api/prediction/risk-1d          — physics-based risk along 1D channel nodes
POST /api/prediction/flood-net        — ML FloodNet risk prediction with confidence (2D)
POST /api/prediction/flood-net-1d     — ML FloodNet risk prediction for 1D channel (new)
GET  /api/prediction/info             — which ML backend is active
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.physics.engine import SimulationEngine
from src.physics.state import Solver1DState, Solver2DState, CoupledState
from src.api.dependencies import get_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["prediction"])


# ── 2D Physics risk grid ───────────────────────────────────────────────────

@router.get("/risk")
async def risk_grid(
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    """
    Return the current physics-based flood risk grid (2D).

    Risk levels: 0=none, 1=minor (≥0.3m), 2=moderate (≥1.0m),
                 3=major (≥2.0m), 4=severe (≥5.0m).
    """
    state_2d = _get_2d_state(engine)
    risk = state_2d.flood_risk.astype(int)
    counts = {str(lvl): int((risk == lvl).sum()) for lvl in range(5)}

    return {
        "nx": state_2d.nx,
        "ny": state_2d.ny,
        "elapsed_time": engine.current_time,
        "risk_grid": risk.tolist(),
        "summary": counts,
        "backend": "physics",
    }


# ── 1D Physics risk profile ────────────────────────────────────────────────

@router.get("/risk-1d")
async def risk_profile_1d(
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    """
    Return physics-based flood risk along 1D channel nodes.

    Risk levels: 0=none, 1=minor, 2=moderate, 3=major, 4=severe.
    """
    state_1d = _get_1d_state(engine)
    risk = _compute_risk_1d(state_1d)
    counts = {str(lvl): int((risk == lvl).sum()) for lvl in range(5)}

    return {
        "n_nodes": state_1d.n_nodes,
        "elapsed_time": engine.current_time,
        "chainage": state_1d.chainage.tolist(),
        "risk_profile": risk.tolist(),
        "discharge": state_1d.discharge.tolist(),
        "velocity": state_1d.velocity.tolist(),
        "summary": counts,
        "backend": "physics",
    }


# ── 2D ML FloodNet prediction ──────────────────────────────────────────────

@router.post("/flood-net")
async def flood_net_predict(
    request: Request,
    steps_ahead: int = 0,
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    """
    Run FloodNet ML inference on the current 2D simulation state.

    Returns per-cell risk labels (0–4) and confidence scores [0–1].
    The backend used ('physics', 'linear', or 'torch') is reported in the
    response so the UI can indicate the prediction quality.

    Args:
        steps_ahead: Future steps to predict (0 = current state).
    """
    state_2d = _get_2d_state(engine)
    predictor = _get_or_create_predictor(request)

    risk, conf = predictor.predict_with_confidence(state_2d, steps_ahead=steps_ahead)

    counts = {str(lvl): int((risk == lvl).sum()) for lvl in range(5)}

    return {
        "nx": state_2d.nx,
        "ny": state_2d.ny,
        "elapsed_time": engine.current_time,
        "steps_ahead": steps_ahead,
        "risk_grid": risk.astype(int).tolist(),
        "confidence": conf.tolist(),
        "summary": counts,
        "backend": predictor.backend,
    }


# ── 1D ML FloodNet prediction ──────────────────────────────────────────────

@router.post("/flood-net-1d")
async def flood_net_predict_1d(
    request: Request,
    steps_ahead: int = 0,
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    """
    Run FloodNet ML inference on the current 1D channel state.

    Extracts per-node features from the 1D solver, normalises them with
    the same stats used during training, runs the model, and returns
    per-node risk labels and confidence.

    Args:
        steps_ahead: Future steps to predict (0 = current state).
    """
    state_1d = _get_1d_state(engine)
    predictor = _get_or_create_predictor(request)

    # Extract 1D features and normalise
    from src.ml.features import extract_features_1d, normalise_features

    X = extract_features_1d(state_1d)
    X_norm, mean, std = normalise_features(X)

    # Use predictor's backend
    risk, conf = predictor.predict_with_confidence_1d(
        state_1d, X_norm, steps_ahead=steps_ahead
    )

    counts = {str(lvl): int((risk == lvl).sum()) for lvl in range(5)}

    return {
        "n_nodes": state_1d.n_nodes,
        "elapsed_time": engine.current_time,
        "steps_ahead": steps_ahead,
        "chainage": state_1d.chainage.tolist(),
        "risk_profile": risk.tolist(),
        "confidence": conf.tolist(),
        "discharge": state_1d.discharge.tolist(),
        "velocity": state_1d.velocity.tolist(),
        "summary": counts,
        "backend": predictor.backend,
    }


# ── Info ───────────────────────────────────────────────────────────────────

@router.get("/info")
async def prediction_info(request: Request) -> dict:
    """Return which ML backend is active and configuration details."""
    predictor = _get_or_create_predictor(request)
    cfg = request.app.state.config
    return {
        "backend": predictor.backend,
        "checkpoint_path": cfg.ml.checkpoint_path,
        "input_features": cfg.ml.architecture.input_features,
        "output_features": cfg.ml.architecture.output_features,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_2d_state(engine: SimulationEngine) -> Solver2DState:
    raw = engine.state
    if isinstance(raw, CoupledState):
        return raw.state_2d
    if isinstance(raw, Solver2DState):
        return raw
    raise HTTPException(
        status_code=422,
        detail="2D risk grid only available for 2D or 1D+2D simulation modes.",
    )


def _get_1d_state(engine: SimulationEngine) -> Solver1DState:
    raw = engine.state
    if isinstance(raw, CoupledState):
        return raw.state_1d
    if isinstance(raw, Solver1DState):
        return raw
    raise HTTPException(
        status_code=422,
        detail="1D risk profile only available for 1D or 1D+2D simulation modes.",
    )


def _compute_risk_1d(state: Solver1DState) -> list[int]:
    """Compute per-node risk 0-4 from 1D hydraulic state."""
    import numpy as np
    A   = state.area
    V   = state.velocity
    eta = state.water_surface_elev
    # Hydraulic depth approx
    top_w = np.maximum(2.0 * np.sqrt(np.maximum(A, 1e-6)), 1e-6)
    h = A / top_w
    bed = eta - h
    speed = np.abs(V)
    c = np.sqrt(9.81 * np.maximum(h, 1e-9))
    fr = speed / c
    # Risk thresholds
    thresholds = [0.0, 0.3, 1.0, 2.0, 5.0]
    risk = []
    for i in range(state.n_nodes):
        d = float(h[i])
        f = float(fr[i])
        if d < thresholds[1]:
            risk.append(0)
        elif d < thresholds[2]:
            risk.append(1)
        elif d < thresholds[3]:
            risk.append(2)
        elif d < thresholds[4] or f < 1.0:
            risk.append(3)
        else:
            risk.append(4)
    return risk


def _get_or_create_predictor(request: Request):
    """Lazily create and cache the ML predictor on app.state."""
    if not hasattr(request.app.state, "ml_predictor") or request.app.state.ml_predictor is None:
        from src.ml.predictors import get_predictor
        cfg = request.app.state.config
        request.app.state.ml_predictor = get_predictor(cfg)
        logger.info(
            "ML predictor created: backend=%s",
            request.app.state.ml_predictor.backend,
        )
    return request.app.state.ml_predictor
