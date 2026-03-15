"""Pydantic v2 schemas for 1D channel network endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SurveyPoint(BaseModel):
    y: float = Field(..., description="Transverse distance from left bank [m]")
    z: float = Field(..., description="Bed elevation [m a.s.l.]")


class CrossSectionModel(BaseModel):
    id: str = Field(..., description="Unique cross-section identifier")
    reach_id: str = Field(..., description="Parent reach identifier")
    chainage: float = Field(..., ge=0, description="Distance along reach [m]")
    survey_points: list[SurveyPoint] = Field(
        ..., min_length=3, description="At least 3 points to define geometry"
    )
    manning_n: float = Field(0.03, gt=0, description="Manning roughness coefficient")
    bank_left_z: float = Field(..., description="Left bank crest elevation [m]")
    bank_right_z: float = Field(..., description="Right bank crest elevation [m]")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "cs_001",
                "reach_id": "ciliwung_upper",
                "chainage": 1500.0,
                "survey_points": [
                    {"y": 0.0, "z": 12.0},
                    {"y": 5.0, "z": 8.5},
                    {"y": 15.0, "z": 8.0},
                    {"y": 25.0, "z": 8.5},
                    {"y": 30.0, "z": 12.0},
                ],
                "manning_n": 0.035,
                "bank_left_z": 12.0,
                "bank_right_z": 12.0,
            }
        }
    }


class ReachModel(BaseModel):
    id: str
    name: str
    upstream_node: str = Field(..., description="ID of upstream boundary/junction node")
    downstream_node: str = Field(..., description="ID of downstream boundary/junction node")
    length: float = Field(..., gt=0, description="Reach length [m]")
    slope: float = Field(..., gt=0, description="Mean bed slope [m/m]")


class BoundaryConditionModel(BaseModel):
    node_id: str
    bc_type: str = Field(
        ...,
        pattern="^(discharge|stage)$",
        description="'discharge' = Q(t) upstream BC | 'stage' = h(t) downstream BC",
    )
    values: list[float] = Field(..., description="Time series values [m³/s or m]")
    times: list[float] = Field(..., description="Corresponding times [s]")


class ChannelNetworkModel(BaseModel):
    reaches: list[ReachModel]
    cross_sections: list[CrossSectionModel]
    boundary_conditions: list[BoundaryConditionModel]


class AddCrossSectionRequest(BaseModel):
    cross_section: CrossSectionModel


class UpdateNetworkRequest(BaseModel):
    network: ChannelNetworkModel
