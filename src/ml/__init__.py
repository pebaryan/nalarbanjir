"""
Nalarbanjir ML layer.

New API (torch-optional):
    from src.ml import get_predictor, FloodNetPredictorBase
    predictor = get_predictor(cfg)
    risk, confidence = predictor.predict_with_confidence(state_2d)

Legacy code (model.py, training.py, prediction.py) requires torch and
is not imported here to avoid ImportError on systems without torch.
"""
from src.ml.predictors import FloodNetPredictorBase, PhysicsBasedPredictor, get_predictor
from src.ml.features import extract_features

__all__ = [
    "FloodNetPredictorBase",
    "PhysicsBasedPredictor",
    "get_predictor",
    "extract_features",
]
