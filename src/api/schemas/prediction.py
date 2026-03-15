"""Pydantic v2 schemas for ML prediction endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["none", "minor", "moderate", "major", "severe"]


class PredictRequest(BaseModel):
    use_current_state: bool = Field(
        True, description="Run inference on the current simulation state"
    )
    steps_ahead: int = Field(
        0, ge=0, description="Predict N simulation steps into the future (0 = current)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"use_current_state": True, "steps_ahead": 0}
        }
    }


class RiskCell(BaseModel):
    """ML prediction result for a single spatial cell."""
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0, le=1, description="Model confidence [0–1]")
    predicted_depth: float = Field(..., ge=0, description="Predicted water depth [m]")
    depth_uncertainty: float = Field(..., ge=0, description="Depth std from MC-Dropout [m]")


class RiskGridResponse(BaseModel):
    """
    Grid of per-cell risk predictions.

    For 2D mode: shape [nx][ny]
    For 1D mode: shape [n_nodes][1]
    """
    mode: str
    step: int
    risk_grid: list[list[RiskCell]]
    summary: dict[str, int] = Field(
        ..., description="Count of cells per risk level: {none: N, minor: N, ...}"
    )


class PredictionHistoryItem(BaseModel):
    step: int
    timestamp: float = Field(..., description="Wall-clock time of prediction [Unix epoch]")
    max_risk: RiskLevel
    flooded_cells: int
    mean_confidence: float = Field(..., ge=0, le=1)


class PredictionHistoryResponse(BaseModel):
    items: list[PredictionHistoryItem]
    total: int
