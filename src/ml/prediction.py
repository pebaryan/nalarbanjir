"""Prediction engine for ML models in Flood Prediction World Model.

This module provides prediction capabilities for trained machine learning models
including uncertainty quantification and ensemble methods.
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class PredictionEngine:
    """Engine for making predictions with ML models.

    Provides methods for generating predictions, handling uncertainty,
    and supporting real-time forecasting with confidence estimation.
    """

    def __init__(self, model: torch.nn.Module, config: Any):
        """Initialize the prediction engine.

        Args:
            model: Trained PyTorch model
            config: Model configuration
        """
        self.model = model
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()  # Set to evaluation mode

        logger.info(f"PredictionEngine initialized on {self.device}")

    def predict(
        self,
        input_data: Dict[str, Any],
        prediction_type: str = "flood_risk",
        return_uncertainty: bool = False,
    ) -> Dict[str, Any]:
        """Generate predictions for the given input data.

        Args:
            input_data: Input data dictionary
            prediction_type: Type of prediction to generate
            return_uncertainty: Whether to return uncertainty estimates

        Returns:
            Prediction results dictionary
        """
        # Prepare input tensor
        tensor_input = self._prepare_input(input_data)

        # Make prediction
        with torch.no_grad():
            model_output = self.model(tensor_input)
            if isinstance(model_output, tuple):
                output = model_output[0]
                # Handle additional outputs like attention weights
                additional_outputs = model_output[1:] if len(model_output) > 1 else []
            else:
                output = model_output
                additional_outputs = []

        # Process output based on prediction type
        if prediction_type == "flood_risk":
            predictions = self._process_flood_risk(output)
        elif prediction_type == "flow_dynamics":
            predictions = self._process_flow_dynamics(output)
        elif prediction_type == "water_quality":
            predictions = self._process_water_quality(output)
        elif prediction_type == "comprehensive":
            predictions = self._process_comprehensive(output)
        else:
            # Default to treating output as raw predictions
            predictions = self._process_raw_output(output)

        # Add uncertainty estimates if requested
        if return_uncertainty:
            predictions["uncertainty"] = self._estimate_uncertainty(tensor_input)

        # Add metadata
        predictions["metadata"] = {
            "prediction_type": prediction_type,
            "timestamp": torch.datetime.now().timestamp()
            if hasattr(torch, "datetime")
            else 0,
            "model_type": getattr(self.config, "model_type", "unknown"),
        }

        return predictions

    def _prepare_input(self, input_data: Dict[str, Any]) -> torch.Tensor:
        """Prepare input data for model inference.

        Args:
            input_data: Input data dictionary

        Returns:
            Prepared input tensor
        """
        # Extract features in the order expected by the model
        features = []

        # Handle different input formats
        if "features" in input_data:
            # Direct feature array
            features = input_data["features"]
        else:
            # Extract individual features
            feature_names = getattr(
                self.config,
                "input_features",
                [
                    "elevation",
                    "permeability",
                    "land_use_type",
                    "water_depth",
                    "velocity_x",
                    "velocity_y",
                    "flow_rate",
                    "flood_index",
                    "precipitation",
                    "seasonal_factor",
                ],
            )

            # If input_features is an integer, use default feature names
            if isinstance(feature_names, int):
                feature_names = [
                    "elevation",
                    "permeability",
                    "land_use_type",
                    "water_depth",
                    "velocity_x",
                    "velocity_y",
                    "flow_rate",
                    "flood_index",
                    "precipitation",
                    "seasonal_factor",
                ][:feature_names]

            for feature_name in feature_names:
                if feature_name in input_data:
                    features.append(input_data[feature_name])
                else:
                    # Provide default values for missing features
                    defaults = {
                        "elevation": 0.0,
                        "permeability": 0.5,
                        "land_use_type": 0,
                        "water_depth": 0.0,
                        "velocity_x": 0.0,
                        "velocity_y": 0.0,
                        "flow_rate": 0.0,
                        "flood_index": 0.0,
                        "precipitation": 0.0,
                        "seasonal_factor": 1.0,
                    }
                    features.append(defaults.get(feature_name, 0.0))

        # Convert to tensor
        input_tensor = torch.tensor([features], dtype=torch.float32)
        return input_tensor.to(self.device)

    def _process_flood_risk(self, output: torch.Tensor) -> Dict[str, Any]:
        """Process output for flood risk prediction.

        Args:
            output: Model output tensor

        Returns:
            Flood risk predictions
        """
        # Apply softmax if not already applied
        if output.shape[-1] > 1:
            probs = torch.softmax(output, dim=-1)
        else:
            # For single output, treat as probability
            probs = torch.sigmoid(output)

        probs = probs.cpu().numpy().flatten()

        # Map to risk levels
        risk_levels = ["low", "moderate", "high", "severe"]
        predictions = {}

        for i, level in enumerate(risk_levels):
            if i < len(probs):
                predictions[level] = {
                    "probability": float(probs[i]),
                    "level": i,
                    "description": self._get_risk_description(level),
                }
            else:
                predictions[level] = {
                    "probability": 0.0,
                    "level": i,
                    "description": self._get_risk_description(level),
                }

        # Determine overall risk level
        max_prob_idx = (
            np.argmax(probs[: len(risk_levels)])
            if len(probs) >= len(risk_levels)
            else 0
        )
        predictions["overall_risk"] = risk_levels[
            min(max_prob_idx, len(risk_levels) - 1)
        ]
        predictions["max_probability"] = (
            float(np.max(probs[: len(risk_levels)]))
            if len(probs) >= len(risk_levels)
            else float(probs[0])
            if len(probs) > 0
            else 0.0
        )

        return predictions

    def _process_flow_dynamics(self, output: torch.Tensor) -> Dict[str, Any]:
        """Process output for flow dynamics prediction.

        Args:
            output: Model output tensor

        Returns:
            Flow dynamics predictions
        """
        output_np = output.cpu().numpy().flatten()

        # Extract flow characteristics
        predictions = {
            "velocity_magnitude": float(np.abs(output_np[0]))
            if len(output_np) > 0
            else 0.0,
            "velocity_direction": float(output_np[1]) if len(output_np) > 1 else 0.0,
            "flow_rate": float(output_np[2]) if len(output_np) > 2 else 0.0,
            "turbulence_level": float(output_np[3]) if len(output_np) > 3 else 0.0,
            "vorticity": float(output_np[4]) if len(output_np) > 4 else 0.0,
        }

        # Classify flow pattern
        vel_mag = predictions["velocity_magnitude"]
        if vel_mag < 0.1:
            predictions["flow_regime"] = "still"
        elif vel_mag < 0.5:
            predictions["flow_regime"] = "laminar"
        elif vel_mag < 1.0:
            predictions["flow_regime"] = "transitional"
        else:
            predictions["flow_regime"] = "turbulent"

        return predictions

    def _process_water_quality(self, output: torch.Tensor) -> Dict[str, Any]:
        """Process output for water quality prediction.

        Args:
            output: Model output tensor

        Returns:
            Water quality predictions
        """
        output_np = output.cpu().numpy().flatten()

        predictions = {
            "ph_level": float(output_np[0]) if len(output_np) > 0 else 7.0,
            "dissolved_oxygen": float(output_np[1]) if len(output_np) > 1 else 8.0,
            "turbidity": float(output_np[2]) if len(output_np) > 2 else 0.0,
            "conductivity": float(output_np[3]) if len(output_np) > 3 else 0.0,
            "temperature": float(output_np[4]) if len(output_np) > 4 else 20.0,
        }

        # Assess water quality
        do_level = predictions["dissolved_oxygen"]
        turbidity = predictions["turbidity"]

        if do_level > 6.0 and turbidity < 10.0:
            predictions["quality_rating"] = "excellent"
        elif do_level > 4.0 and turbidity < 30.0:
            predictions["quality_rating"] = "good"
        elif do_level > 2.0 and turbidity < 100.0:
            predictions["quality_rating"] = "fair"
        else:
            predictions["quality_rating"] = "poor"

        return predictions

    def _process_comprehensive(self, output: torch.Tensor) -> Dict[str, Any]:
        """Process output for comprehensive prediction.

        Args:
            output: Model output tensor

        Returns:
            Combined predictions
        """
        # For comprehensive output, assume it contains multiple prediction types
        # Split the output appropriately
        output_np = output.cpu().numpy().flatten()

        # Allocate outputs: first 4 for flood risk, next 5 for flow dynamics, etc.
        flood_risk_output = (
            torch.tensor(output_np[:4]) if len(output_np) >= 4 else output
        )
        flow_output = (
            torch.tensor(output_np[4:9])
            if len(output_np) >= 9
            else torch.tensor([0.0] * 5)
        )
        water_quality_output = (
            torch.tensor(output_np[9:14])
            if len(output_np) >= 14
            else torch.tensor([0.0] * 5)
        )

        # Process each component
        predictions = {}
        predictions.update(self._process_flood_risk(flood_risk_output.unsqueeze(0)))
        predictions.update(self._process_flow_dynamics(flow_output.unsqueeze(0)))
        predictions.update(
            self._process_water_quality(water_quality_output.unsqueeze(0))
        )

        predictions["prediction_type"] = "comprehensive"

        return predictions

    def _process_raw_output(self, output: torch.Tensor) -> Dict[str, Any]:
        """Process raw output tensor.

        Args:
            output: Model output tensor

        Returns:
            Raw predictions
        """
        output_np = output.cpu().numpy().flatten()

        return {
            "raw_values": output_np.tolist(),
            "shape": list(output.shape),
            "max_value": float(np.max(output_np)) if len(output_np) > 0 else 0.0,
            "min_value": float(np.min(output_np)) if len(output_np) > 0 else 0.0,
            "mean_value": float(np.mean(output_np)) if len(output_np) > 0 else 0.0,
        }

    def _get_risk_description(self, level: str) -> str:
        """Get description for risk level.

        Args:
            level: Risk level string

        Returns:
            Description of the risk level
        """
        descriptions = {
            "low": "Minimal flood risk - water levels within normal bounds",
            "moderate": "Moderate flood risk - elevated water levels possible",
            "high": "High flood risk - significant flooding possible",
            "severe": "Severe flood risk - major flooding likely",
        }
        return descriptions.get(level, "Unknown risk level")

    def _estimate_uncertainty(self, input_tensor: torch.Tensor) -> Dict[str, float]:
        """Estimate prediction uncertainty.

        Args:
            input_tensor: Input tensor

        Returns:
            Uncertainty estimates
        """
        # Simple uncertainty estimation based on model confidence
        # In a more sophisticated implementation, this could use:
        # - Monte Carlo dropout
        # - Ensemble methods
        # - Bayesian neural networks

        with torch.no_grad():
            # Get prediction
            output = self.model(input_tensor)
            if isinstance(output, tuple):
                output = output[0]

            # For classification, uncertainty can be entropy of softmax
            if output.shape[-1] > 1:
                probs = torch.softmax(output, dim=-1)
                # Entropy as uncertainty measure
                entropy = -torch.sum(probs * torch.log(probs + 1e-8), dim=-1)
                uncertainty = float(entropy.mean())
            else:
                # For regression, use distance from decision boundary as proxy
                # Simplified: uncertainty increases with distance from 0.5
                probs = torch.sigmoid(output)
                uncertainty = float(torch.mean(torch.abs(probs - 0.5)))

            return {
                "entropy": uncertainty,
                "confidence": 1.0 - min(uncertainty, 1.0),
                "method": "softmax_entropy"
                if output.shape[-1] > 1
                else "distance_from_boundary",
            }

    def predict_batch(
        self, input_data_list: List[Dict[str, Any]], prediction_type: str = "flood_risk"
    ) -> List[Dict[str, Any]]:
        """Make predictions for a batch of input data.

        Args:
            input_data_list: List of input data dictionaries
            prediction_type: Type of prediction to generate

        Returns:
            List of prediction results
        """
        results = []
        for input_data in input_data_list:
            result = self.predict(input_data, prediction_type)
            results.append(result)
        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model.

        Returns:
            Model information dictionary
        """
        info = {
            "model_type": getattr(self.config, "model_type", "unknown"),
            "device": str(self.device),
            "parameters": sum(p.numel() for p in self.model.parameters()),
            "trainable_parameters": sum(
                p.numel() for p in self.model.parameters() if p.requires_grad
            ),
            "layers": len(list(self.model.modules())),
        }

        # Add input/output info if available
        if hasattr(self.config, "input_features"):
            info["input_features"] = self.config.input_features
        if hasattr(self.config, "output_features"):
            info["output_features"] = self.config.output_features

        return info


# Factory function for easy engine creation
def create_prediction_engine(model: torch.nn.Module, config: Any) -> PredictionEngine:
    """Create a prediction engine with default settings.

    Args:
        model: Trained PyTorch model
        config: Model configuration

    Returns:
        Configured PredictionEngine instance
    """
    return PredictionEngine(model, config)
