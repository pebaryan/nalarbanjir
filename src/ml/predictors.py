"""
FloodNet predictor classes.

Three implementations share the same interface:

  PhysicsBasedPredictor  — reads flood_risk directly from the physics state
                           (no ML; used as a fast baseline and fallback)

  LinearFloodPredictor   — a simple logistic regression trained on features
                           (numpy-only; no torch required)

  TorchFloodPredictor    — loads a PyTorch checkpoint if available
                           (requires torch; falls back to LinearFloodPredictor)

Usage:
    predictor = get_predictor(config)
    risk, conf = predictor.predict_with_confidence(state_2d)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from src.core.config import NalarbanjirConfig
from src.physics.state import Solver2DState
from src.ml.features import extract_features

logger = logging.getLogger(__name__)

# Risk thresholds (depth in metres) matching the physics solver
_THRESHOLDS = [0.0, 0.3, 1.0, 2.0, 5.0]   # 0=none,1=minor,2=moderate,3=major,4=severe


# ── Abstract base ─────────────────────────────────────────────────────────

class FloodNetPredictorBase(ABC):
    """Common interface for all flood risk predictors."""

    @abstractmethod
    def predict(self, state: Solver2DState, steps_ahead: int = 0) -> np.ndarray:
        """Return integer risk labels (0–4), shape (nx, ny)."""
        ...

    @abstractmethod
    def predict_with_confidence(
        self, state: Solver2DState, steps_ahead: int = 0
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (risk_labels, confidence), both shape (nx, ny), float32."""
        ...

    @property
    @abstractmethod
    def backend(self) -> str:
        """Short identifier: 'physics', 'linear', or 'torch'."""
        ...


# ── Physics-based fallback ────────────────────────────────────────────────

class PhysicsBasedPredictor(FloodNetPredictorBase):
    """
    Reads flood_risk directly from the physics state.

    This is always available (no ML required) and serves as the production
    baseline until a trained model is available.
    """

    @property
    def backend(self) -> str:
        return "physics"

    def predict(self, state: Solver2DState, steps_ahead: int = 0) -> np.ndarray:
        return state.flood_risk.astype(np.int8)

    def predict_with_confidence(
        self, state: Solver2DState, steps_ahead: int = 0
    ) -> tuple[np.ndarray, np.ndarray]:
        risk = state.flood_risk.astype(np.float32)
        # Physics-based predictions have 100% confidence (they're exact by definition)
        confidence = np.ones_like(risk)
        return risk.astype(np.int8), confidence


# ── Linear (numpy) predictor ──────────────────────────────────────────────

class LinearFloodPredictor(FloodNetPredictorBase):
    """
    Multi-class logistic regression on the 10 physics features.

    Trained at init from a small rule-based synthetic dataset so it gives
    plausible outputs even without a real checkpoint.  A real checkpoint
    (weights.npz) can be loaded to replace the synthetic weights.
    """

    N_FEATURES = 10
    N_CLASSES  = 5

    def __init__(self, weights_path: Path | None = None) -> None:
        self._W: np.ndarray  # (n_features, n_classes)
        self._b: np.ndarray  # (n_classes,)

        if weights_path and weights_path.exists():
            data = np.load(str(weights_path))
            self._W = data["W"].astype(np.float32)
            self._b = data["b"].astype(np.float32)
            logger.info("Loaded linear weights from %s", weights_path)
        else:
            self._W, self._b = self._synthetic_weights()

    @property
    def backend(self) -> str:
        return "linear"

    def predict(self, state: Solver2DState, steps_ahead: int = 0) -> np.ndarray:
        probs = self._forward(state)
        return np.argmax(probs, axis=-1).reshape(state.nx, state.ny).astype(np.int8)

    def predict_with_confidence(
        self, state: Solver2DState, steps_ahead: int = 0
    ) -> tuple[np.ndarray, np.ndarray]:
        probs = self._forward(state)
        risk = np.argmax(probs, axis=-1).reshape(state.nx, state.ny).astype(np.int8)
        conf = np.max(probs, axis=-1).reshape(state.nx, state.ny).astype(np.float32)
        return risk, conf

    # ── Internal ──────────────────────────────────────────────────────────

    def _forward(self, state: Solver2DState) -> np.ndarray:
        """Softmax logistic regression: (nx*ny, n_classes)."""
        X = extract_features(state)   # (n_cells, 10)
        logits = X @ self._W + self._b
        return _softmax(logits)

    @staticmethod
    def _synthetic_weights() -> tuple[np.ndarray, np.ndarray]:
        """
        Hand-crafted weights that encode the depth-threshold rules:
          feature 0 (depth) drives the risk class prediction.
        """
        n_f, n_c = LinearFloodPredictor.N_FEATURES, LinearFloodPredictor.N_CLASSES
        W = np.zeros((n_f, n_c), dtype=np.float32)
        b = np.zeros(n_c, dtype=np.float32)

        # Depth feature (index 0) → logits for each class
        # class 0 (none):     decreasing in h
        # class 1 (minor):    peaks near h=0.3
        # class 2 (moderate): peaks near h=1.0
        # class 3 (major):    peaks near h=2.0
        # class 4 (severe):   increasing for large h
        W[0, 0] = -4.0   # none: low depth
        W[0, 1] =  2.0   # minor
        W[0, 2] =  1.5   # moderate
        W[0, 3] =  1.0   # major
        W[0, 4] =  0.5   # severe
        b[0] = 2.0        # bias toward none when h≈0

        # Froude number (index 6) — higher Fr → higher risk
        W[6, 2] = 0.5
        W[6, 3] = 1.0
        W[6, 4] = 1.5

        return W, b


# ── Torch predictor (optional) ────────────────────────────────────────────

class TorchFloodPredictor(FloodNetPredictorBase):
    """
    Loads a pretrained PyTorch checkpoint and runs inference.

    Falls back to LinearFloodPredictor if torch is unavailable or the
    checkpoint doesn't exist.
    """

    def __init__(self, checkpoint_path: Path, config: NalarbanjirConfig) -> None:
        self._fallback = LinearFloodPredictor()
        self._model = None
        self._cfg = config

        try:
            import torch
            import torch.nn as nn

            cp = checkpoint_path
            if not cp.exists():
                logger.warning(
                    "Checkpoint %s not found — using linear predictor", cp
                )
                return

            class _FloodNetMLP(nn.Module):
                def __init__(self, in_f: int, n_classes: int):
                    super().__init__()
                    h = config.ml.architecture.hidden_dims
                    dims = [in_f] + list(h) + [n_classes]
                    layers = []
                    for a, b in zip(dims[:-1], dims[1:]):
                        layers += [nn.Linear(a, b), nn.ReLU()]
                    layers.pop()   # remove last ReLU before logits
                    self.net = nn.Sequential(*layers)

                def forward(self, x):
                    return self.net(x)

            model = _FloodNetMLP(
                in_f=config.ml.architecture.input_features,
                n_classes=config.ml.architecture.output_features,
            )
            model.load_state_dict(torch.load(str(cp), map_location="cpu"))
            model.eval()
            self._model = model
            self._torch = torch
            logger.info("Loaded PyTorch FloodNet from %s", cp)

        except ImportError:
            logger.info("torch not available — using linear predictor")
        except Exception as exc:
            logger.warning("Failed to load checkpoint: %s — using linear predictor", exc)

    @property
    def backend(self) -> str:
        return "torch" if self._model is not None else "linear"

    def predict(self, state: Solver2DState, steps_ahead: int = 0) -> np.ndarray:
        if self._model is None:
            return self._fallback.predict(state, steps_ahead)
        probs = self._torch_forward(state)
        return np.argmax(probs, axis=-1).reshape(state.nx, state.ny).astype(np.int8)

    def predict_with_confidence(
        self, state: Solver2DState, steps_ahead: int = 0
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._model is None:
            return self._fallback.predict_with_confidence(state, steps_ahead)

        # Monte-Carlo Dropout for uncertainty quantification
        n_passes = self._cfg.ml.inference.mc_dropout_passes
        all_probs = []
        import torch

        X = torch.tensor(extract_features(state))
        with torch.no_grad():
            self._model.train()   # enable dropout for MC passes
            for _ in range(n_passes):
                logits = self._model(X)
                all_probs.append(_softmax(logits.numpy()))
            self._model.eval()

        probs_stack = np.stack(all_probs, axis=0)   # (n_passes, n_cells, n_classes)
        mean_probs  = probs_stack.mean(axis=0)
        risk = np.argmax(mean_probs, axis=-1).reshape(state.nx, state.ny).astype(np.int8)
        conf = np.max(mean_probs, axis=-1).reshape(state.nx, state.ny).astype(np.float32)
        return risk, conf

    def _torch_forward(self, state: Solver2DState) -> np.ndarray:
        import torch
        X = torch.tensor(extract_features(state))
        with torch.no_grad():
            self._model.eval()
            logits = self._model(X)
        return _softmax(logits.numpy())


# ── Factory ───────────────────────────────────────────────────────────────

def get_predictor(config: NalarbanjirConfig) -> FloodNetPredictorBase:
    """
    Return the best available predictor given the config.

    Priority:
      1. TorchFloodPredictor  (if torch is installed and checkpoint exists)
      2. LinearFloodPredictor (numpy weights)
      3. PhysicsBasedPredictor (always works — no checkpoint needed)
    """
    cp = Path(config.ml.checkpoint_path)
    try:
        import torch  # noqa: F401 — just check availability
        predictor = TorchFloodPredictor(cp, config)
        return predictor
    except ImportError:
        pass

    weights = cp.parent / "floodnet_linear_weights.npz"
    return LinearFloodPredictor(weights_path=weights if weights.exists() else None)


# ── Helpers ───────────────────────────────────────────────────────────────

def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable row-wise softmax."""
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)
