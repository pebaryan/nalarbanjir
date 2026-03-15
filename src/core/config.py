"""
Nalarbanjir configuration — loads config/model_config.yaml into typed Pydantic models.

Usage:
    from src.core.config import get_config
    cfg = get_config()
    print(cfg.physics.solver_2d.nx)
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

# ── Sub-models ────────────────────────────────────────────────────────────


class Solver1DConfig(BaseModel):
    theta: float = Field(0.6, ge=0.5, le=1.0, description="Preissmann weight")
    dt: float = Field(10.0, gt=0, description="Time step [s]")
    tolerance: float = Field(1e-6, gt=0, description="Newton-Raphson tolerance")
    max_iterations: int = Field(50, gt=0)
    default_manning_n: float = Field(0.03, gt=0)


class Solver2DConfig(BaseModel):
    dt: float = Field(1.0, gt=0, description="Initial time step [s], auto-adjusted by CFL")
    cfl: float = Field(0.9, gt=0, le=1.0, description="CFL safety factor")
    dx: float = Field(100.0, gt=0, description="Cell size x [m]")
    dy: float = Field(100.0, gt=0, description="Cell size y [m]")
    nx: int = Field(100, gt=0, description="Number of cells in x")
    ny: int = Field(100, gt=0, description="Number of cells in y")
    min_depth: float = Field(0.001, gt=0, description="Wet/dry threshold [m]")
    domain_x: float = Field(10000.0, gt=0, description="Domain width [m]")
    domain_y: float = Field(10000.0, gt=0, description="Domain height [m]")


class CouplingConfig(BaseModel):
    weir_coefficient: float = Field(0.4, gt=0, description="Broad-crested weir Cd")
    sync_interval: int = Field(1, gt=0, description="Exchange every N 2D steps")


class PhysicsConfig(BaseModel):
    gravity: float = Field(9.81, gt=0)
    default_mode: Literal["1d", "2d", "1d2d"] = "2d"
    solver_1d: Solver1DConfig = Field(default_factory=Solver1DConfig)
    solver_2d: Solver2DConfig = Field(default_factory=Solver2DConfig)
    coupling: CouplingConfig = Field(default_factory=CouplingConfig)


class FloodThresholdsConfig(BaseModel):
    minor: float = Field(0.3, gt=0)
    moderate: float = Field(1.0, gt=0)
    major: float = Field(2.0, gt=0)
    severe: float = Field(5.0, gt=0)

    @field_validator("severe")
    @classmethod
    def thresholds_ascending(cls, v: float, info) -> float:
        data = info.data
        if "major" in data and v <= data["major"]:
            raise ValueError("severe threshold must be > major")
        return v


class ManningNConfig(BaseModel):
    water: float = Field(0.025, gt=0)
    urban: float = Field(0.015, gt=0)
    agricultural: float = Field(0.035, gt=0)
    forest: float = Field(0.100, gt=0)
    wetland: float = Field(0.050, gt=0)
    open_land: float = Field(0.030, gt=0)


class LandUseTypeConfig(BaseModel):
    permeability: float = Field(..., ge=0, le=1)
    vulnerability: int = Field(..., ge=1, le=5)


class TerrainConfig(BaseModel):
    initial_water_depth: float = Field(0.0, ge=0)
    amplitude: float = Field(2.0, gt=0, description="Synthetic DEM amplitude [m]")
    wavelength: float = Field(2000.0, gt=0, description="Synthetic DEM wavelength [m]")
    manning_n: ManningNConfig = Field(default_factory=ManningNConfig)
    flood_thresholds: FloodThresholdsConfig = Field(default_factory=FloodThresholdsConfig)
    land_use: dict[str, LandUseTypeConfig] = Field(default_factory=dict)


class StormCellConfig(BaseModel):
    sigma: float = Field(2000.0, gt=0, description="Gaussian spread [m]")


class RainfallConfig(BaseModel):
    default_type: Literal["uniform", "storm_cell", "frontal"] = "uniform"
    default_intensity: float = Field(0.0, ge=0, description="Rainfall intensity [m/s]")
    storm_cell: StormCellConfig = Field(default_factory=StormCellConfig)


class MLArchitectureConfig(BaseModel):
    input_features: int = Field(10, gt=0)
    output_features: int = Field(5, gt=0)
    hidden_dims: list[int] = Field(default_factory=lambda: [64, 128, 256])
    n_heads: int = Field(4, gt=0)
    dropout: float = Field(0.1, ge=0, lt=1)


class MLTrainingConfig(BaseModel):
    learning_rate: float = Field(0.001, gt=0)
    batch_size: int = Field(32, gt=0)
    epochs: int = Field(100, gt=0)
    patience: int = Field(10, gt=0)
    validation_split: float = Field(0.2, gt=0, lt=1)


class MLInferenceConfig(BaseModel):
    mc_dropout_passes: int = Field(50, gt=0, description="Monte Carlo Dropout passes for UQ")
    batch_size: int = Field(256, gt=0)


class MLConfig(BaseModel):
    model_type: str = "flood_net"
    checkpoint_path: str = "ml/checkpoints/floodnet_v2.pt"
    architecture: MLArchitectureConfig = Field(default_factory=MLArchitectureConfig)
    training: MLTrainingConfig = Field(default_factory=MLTrainingConfig)
    inference: MLInferenceConfig = Field(default_factory=MLInferenceConfig)


class SimulationConfig(BaseModel):
    total_steps: int = Field(1000, gt=0)
    save_every: int = Field(100, gt=0)
    log_every: int = Field(10, gt=0)
    broadcast_interval: int = Field(5, gt=0, description="WS update every N steps")


class WebSocketConfig(BaseModel):
    url: str = "/ws"
    heartbeat_interval: int = Field(30, gt=0, description="Heartbeat interval [s]")
    max_connections: int = Field(100, gt=0)


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(8000, gt=0, lt=65536)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)


class LoggingFilesConfig(BaseModel):
    simulation: str = "logs/simulation.log"
    errors: str = "logs/errors.log"
    access: str = "logs/access.log"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    files: LoggingFilesConfig = Field(default_factory=LoggingFilesConfig)


class DataStorageConfig(BaseModel):
    primary: str = "data/primary"
    archive: str = "data/archive"


class DataConfig(BaseModel):
    storage: DataStorageConfig = Field(default_factory=DataStorageConfig)
    formats: list[str] = Field(default_factory=lambda: ["json", "csv", "netcdf", "hdf5"])


class PerformanceLimitsConfig(BaseModel):
    max_memory_gb: int = Field(4, gt=0)
    max_cpu_percent: int = Field(80, gt=0, le=100)
    max_connections: int = Field(1000, gt=0)


class PerformanceConfig(BaseModel):
    limits: PerformanceLimitsConfig = Field(default_factory=PerformanceLimitsConfig)
    caching: bool = True


class AppConfig(BaseModel):
    name: str = "nalarbanjir"
    version: str = "2.0.0"
    description: str = ""


# ── Root config ───────────────────────────────────────────────────────────


class NalarbanjirConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    rainfall: RainfallConfig = Field(default_factory=RainfallConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)


# ── Loader ────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "model_config.yaml"
_config: NalarbanjirConfig | None = None


def load_config(path: Path | None = None) -> NalarbanjirConfig:
    """Load and validate config from YAML. Caches result globally."""
    global _config
    yaml_path = path or _CONFIG_PATH
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    _config = NalarbanjirConfig.model_validate(raw or {})
    return _config


def get_config() -> NalarbanjirConfig:
    """Return cached config, loading from default path if not yet loaded."""
    if _config is None:
        return load_config()
    return _config
