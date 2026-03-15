"""
Flood risk prediction endpoints.

GET  /api/prediction/risk      — physics-based risk grid (fast, no ML)
POST /api/prediction/flood-net — ML FloodNet risk prediction with confidence
GET  /api/prediction/info      — which ML backend is active
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.physics.engine import SimulationEngine
from src.physics.state import Solver2DState, CoupledState
from src.api.dependencies import get_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["prediction"])


# ── Physics risk grid ──────────────────────────────────────────────────────

@router.get("/risk")
async def risk_grid(
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    """
    Return the current physics-based flood risk grid.

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


# ── ML FloodNet prediction ─────────────────────────────────────────────────

@router.post("/flood-net")
async def flood_net_predict(
    request: Request,
    steps_ahead: int = 0,
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    """
    Run FloodNet ML inference on the current simulation state.

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
        detail="Risk grid only available for 2D or 1D+2D simulation modes.",
    )


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
