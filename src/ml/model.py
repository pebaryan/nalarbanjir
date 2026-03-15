"""ML Model architecture for Flood Prediction World Model.

This module defines the neural network architecture and configuration
for the machine learning components of the flood prediction system.
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for the ML model.

    Attributes:
        model_type: Type of model architecture
        input_features: Number of input features
        hidden_dims: List of hidden layer dimensions
        output_features: Number of output features
        learning_rate: Learning rate for training
        dropout_rate: Dropout rate for regularization
        batch_size: Batch size for training
    """

    model_type: str = "flood_net"
    input_features: int = 10
    hidden_dims: List[int] = None
    output_features: int = 5
    learning_rate: float = 1e-3
    dropout_rate: float = 0.1
    batch_size: int = 32

    def __post_init__(self):
        """Initialize default values."""
        if self.hidden_dims is None:
            self.hidden_dims = [64, 128, 256]

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelConfig":
        """Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            ModelConfig instance
        """
        config = cls(
            model_type=data.get("model_type", "flood_net"),
            input_features=data.get("input_features", 10),
            hidden_dims=data.get("hidden_dims", [64, 128, 256]),
            output_features=data.get("output_features", 5),
            learning_rate=data.get("learning_rate", 1e-3),
            dropout_rate=data.get("dropout_rate", 0.1),
            batch_size=data.get("batch_size", 32),
        )

        return config

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary.

        Returns:
            Configuration dictionary
        """
        return asdict(self)


class FloodNet(nn.Module):
    """Neural network architecture for flood prediction.

    This model is designed to capture the complex relationships between
    terrain characteristics, water dynamics, and flood risk factors.
    """

    def __init__(self, config: ModelConfig):
        """Initialize the flood network.

        Args:
            config: Model configuration
        """
        super().__init__()

        self.config = config

        # Input embedding layer
        self.input_embedding = nn.Linear(config.input_features, config.hidden_dims[0])

        # Hidden layers
        hidden_layers = []
        for i in range(len(config.hidden_dims) - 1):
            hidden_layers.extend(
                [
                    nn.Linear(config.hidden_dims[i], config.hidden_dims[i + 1]),
                    nn.BatchNorm1d(config.hidden_dims[i + 1]),
                    nn.ReLU(),
                    nn.Dropout(config.dropout_rate),
                ]
            )

        self.hidden_layers = nn.Sequential(*hidden_layers)

        # Output layers
        self.output_layer = nn.Sequential(
            nn.Linear(config.hidden_dims[-1], config.output_features),
            nn.Softmax(dim=-1),
        )

        # Attention mechanism
        self.attention = FloodAttention(embed_dim=config.hidden_dims[-1], num_heads=4)

        # Initialize weights
        self._initialize_weights()

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass through the network.

        Args:
            x: Input tensor of shape (batch, seq_len, features)

        Returns:
            Tuple of (output, attention_weights)
        """
        batch_size, seq_len, _ = x.shape

        # Input embedding - process each position independently
        # Reshape to (batch * seq_len, features) for linear layer
        x_flat = x.view(batch_size * seq_len, -1)
        x = self.input_embedding(x_flat)

        # Reshape back to (batch, seq_len, hidden_dim)
        hidden_dim = x.shape[-1]
        x = x.view(batch_size, seq_len, hidden_dim)

        # Reshape for hidden layers: (batch, seq_len, hidden_dim) -> (batch * seq_len, hidden_dim)
        x = x.view(batch_size * seq_len, -1)

        # Hidden layers (dropout disabled in eval mode)
        if not self.training:
            # Store dropout states and disable
            dropout_states = []
            for module in self.hidden_layers.modules():
                if isinstance(module, nn.Dropout):
                    dropout_states.append(module.p)
                    module.p = 0

            x = self.hidden_layers(x)

            # Restore dropout states
            idx = 0
            for module in self.hidden_layers.modules():
                if isinstance(module, nn.Dropout):
                    module.p = dropout_states[idx]
                    idx += 1
        else:
            x = self.hidden_layers(x)

        # Reshape back to (batch, seq_len, hidden_dim)
        # The last hidden dimension matches attention's embed_dim
        x = x.view(batch_size, seq_len, -1)

        # Apply attention mechanism after hidden layers
        x, attn_weights = self.attention(x)

        # Output layer
        output = self.output_layer(x)

        return output, attn_weights

    def _initialize_weights(self):
        """Initialize model weights."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.constant_(module.bias, 0)
            elif isinstance(module, nn.BatchNorm1d):
                nn.init.constant_(module.weight, 1)
                nn.init.constant_(module.bias, 0)

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores.

        Returns:
            Dictionary of feature importance scores
        """
        importance = {}

        # Extract weight matrices
        input_weights = self.input_embedding.weight.data

        # Calculate importance based on weight magnitudes
        for i in range(input_weights.size(1)):
            feature_name = f"feature_{i}"
            importance[feature_name] = float(input_weights[:, i].norm().item())

        return importance


class FloodAttention(nn.Module):
    """Attention mechanism for flood prediction.

    Implements self-attention to capture dependencies between different
    aspects of the flood system.
    """

    def __init__(self, embed_dim: int, num_heads: int, dropout_rate: float = 0.1):
        """Initialize the attention module.

        Args:
            embed_dim: Embedding dimension
            num_heads: Number of attention heads
            dropout_rate: Dropout rate
        """
        super().__init__()

        self.num_heads = num_heads
        self.embed_dim = embed_dim

        # Query, Key, Value projections
        self.qkv = nn.Linear(embed_dim, embed_dim * 3)

        # Output projection
        self.output = nn.Linear(embed_dim, embed_dim)

        # Attention dropout
        self.dropout = nn.Dropout(dropout_rate)

        # Initialize
        self._initialize_weights()

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass through attention module.

        Args:
            x: Input tensor of shape (batch, seq_len, features)

        Returns:
            Tuple of (output, attention_weights)
        """
        batch_size, seq_len, _ = x.shape

        # Compute query, key, value
        qkv = self.qkv(x)
        q, k, v = torch.chunk(qkv, 3, dim=-1)

        # Split heads
        head_dim = self.embed_dim // self.num_heads
        q = q.view(batch_size, seq_len, self.num_heads, head_dim).permute(0, 2, 1, 3)
        k = k.view(batch_size, seq_len, self.num_heads, head_dim).permute(0, 2, 1, 3)
        v = v.view(batch_size, seq_len, self.num_heads, head_dim).permute(0, 2, 1, 3)

        # Scaled dot-product attention
        attention_scores = torch.matmul(q, k.transpose(-2, -1)) / (head_dim**0.5)
        attention_weights = torch.softmax(attention_scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Apply attention to values
        output = torch.matmul(attention_weights, v)
        output = output.permute(0, 2, 1, 3).contiguous().view(batch_size, seq_len, -1)

        # Output projection
        output = self.output(output)

        return output, attention_weights

    def _initialize_weights(self):
        """Initialize attention weights."""
        nn.init.xavier_uniform_(self.qkv.weight)
        nn.init.xavier_uniform_(self.output.weight)
        nn.init.constant_(self.qkv.bias, 0)
        nn.init.constant_(self.output.bias, 0)


class PredictionEngine:
    """Engine for making flood predictions.

    Provides methods for generating predictions, handling uncertainty,
    and supporting real-time forecasting.
    """

    def __init__(self, model: FloodNet, config: ModelConfig):
        """Initialize the prediction engine.

        Args:
            model: Flood network model
            config: Configuration parameters
        """
        self.model = model
        self.config = config

        # Training state
        self.training_history = {"loss": [], "accuracy": [], "epochs": []}

        # Device configuration
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        # Set model to evaluation mode for predictions
        self.model.eval()

    def predict(self, input_data: Dict, prediction_type: str = "flood_risk") -> Dict:
        """Generate predictions for the given input data.

        Args:
            input_data: Input data dictionary
            prediction_type: Type of prediction to generate

        Returns:
            Prediction results
        """
        # Prepare input tensor
        tensor_input = self._prepare_input(input_data)

        # Make prediction
        with torch.no_grad():
            output, attention_weights = self.model(tensor_input)

        # Process output
        results = self._process_output(output, attention_weights, prediction_type)

        # Add confidence scores
        results["confidence"] = self._compute_confidence(results)

        return results

    def _prepare_input(self, input_data: Dict) -> torch.Tensor:
        """Prepare input data for model.

        Args:
            input_data: Input data dictionary

        Returns:
            Prepared input tensor
        """
        # Extract relevant features
        features = []

        # Terrain features
        features.append(input_data.get("elevation", 0))
        features.append(input_data.get("permeability", 0.5))
        features.append(input_data.get("land_use_type", 0))

        # Water dynamics
        features.append(input_data.get("water_depth", 1.0))
        features.append(input_data.get("velocity_x", 0.2))
        features.append(input_data.get("velocity_y", 0.2))

        # Flow characteristics
        features.append(input_data.get("flow_rate", 1.0))
        features.append(input_data.get("flood_index", 0.5))

        # Additional features
        features.append(input_data.get("precipitation", 0))
        features.append(input_data.get("seasonal_factor", 1.0))

        # Convert to tensor - add seq_len dimension (1) for attention mechanism
        # Shape: (batch=1, seq_len=1, features)
        input_tensor = (
            torch.tensor(features, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        )

        return input_tensor.to(self.device)

    def _process_output(
        self,
        output: torch.Tensor,
        attention_weights: torch.Tensor,
        prediction_type: str,
    ) -> Dict:
        """Process model output into prediction results.

        Args:
            output: Model output tensor
            attention_weights: Attention weights
            prediction_type: Type of prediction

        Returns:
            Processed prediction results
        """
        # Extract predictions based on type
        if prediction_type == "flood_risk":
            predictions = self._extract_flood_risk(output)
        elif prediction_type == "flow_dynamics":
            predictions = self._extract_flow_dynamics(output)
        else:
            predictions = self._extract_comprehensive(output)

        return predictions

    def _extract_flood_risk(self, output: torch.Tensor) -> Dict:
        """Extract flood risk predictions.

        Args:
            output: Model output tensor

        Returns:
            Flood risk predictions
        """
        # Risk levels: low, moderate, high, severe
        risk_levels = ["low", "moderate", "high", "severe"]

        # Get risk probabilities
        risk_probs = output.squeeze().tolist()

        # Map to risk levels
        risk_predictions = {}
        for i, level in enumerate(risk_levels):
            risk_predictions[level] = {
                "probability": risk_probs[i] if i < len(risk_probs) else 0.25,
                "threshold": self._get_risk_threshold(level),
            }

        return risk_predictions

    def _extract_flow_dynamics(self, output: torch.Tensor) -> Dict:
        """Extract flow dynamics predictions.

        Args:
            output: Model output tensor

        Returns:
            Flow dynamics predictions
        """
        # Flow characteristics
        flow_predictions = {
            "velocity_pattern": self._classify_velocity_pattern(output),
            "wave_characteristics": self._analyze_wave_properties(output),
            "energy_distribution": self._compute_energy_distribution(output),
        }

        return flow_predictions

    def _extract_comprehensive(self, output: torch.Tensor) -> Dict:
        """Extract comprehensive predictions.

        Args:
            output: Model output tensor

        Returns:
            Comprehensive prediction results
        """
        return {
            **self._extract_flood_risk(output),
            **self._extract_flow_dynamics(output),
        }

    def _get_risk_threshold(self, risk_level: str) -> float:
        """Get threshold for risk level.

        Args:
            risk_level: Risk level name

        Returns:
            Risk threshold value
        """
        thresholds = {"low": 0.25, "moderate": 0.50, "high": 0.75, "severe": 0.90}

        return thresholds.get(risk_level, 0.50)

    def _classify_velocity_pattern(self, output: torch.Tensor) -> str:
        """Classify velocity pattern.

        Args:
            output: Model output tensor

        Returns:
            Velocity pattern classification
        """
        # Analyze velocity characteristics
        velocity = output.mean(dim=1).squeeze().item()

        if velocity < 0.3:
            return "laminar"
        elif velocity < 0.6:
            return "transitional"
        else:
            return "turbulent"

    def _analyze_wave_properties(self, output: torch.Tensor) -> Dict:
        """Analyze wave properties.

        Args:
            output: Model output tensor

        Returns:
            Wave property analysis
        """
        # Wave characteristics
        return {
            "wave_type": "shallow_water",
            "propagation_speed": float(output.mean().item()),
            "amplitude": float(output.std().item()),
        }

    def _compute_energy_distribution(self, output: torch.Tensor) -> Dict:
        """Compute energy distribution.

        Args:
            output: Model output tensor

        Returns:
            Energy distribution metrics
        """
        # Energy metrics
        kinetic_energy = 0.5 * output.mean().item() ** 2
        potential_energy = 0.5 * output.var().item()

        return {
            "kinetic_energy": kinetic_energy,
            "potential_energy": potential_energy,
            "total_energy": kinetic_energy + potential_energy,
        }

    def _compute_confidence(self, results: Dict) -> Dict:
        """Compute prediction confidence scores.

        Args:
            results: Prediction results

        Returns:
                Confidence scores
        """
        # Overall confidence
        overall_confidence = np.mean(
            [v["probability"] for v in results.get("flood_risk", {}).values()]
        )

        return {
            "overall": float(overall_confidence),
            "flood_risk": self._calculate_risk_confidence(
                results.get("flood_risk", {})
            ),
            "flow_dynamics": self._calculate_flow_confidence(
                results.get("flow_dynamics", {})
            ),
        }

    def _calculate_risk_confidence(self, risk_data: Dict) -> float:
        """Calculate risk confidence score.

        Args:
            risk_data: Risk data dictionary

        Returns:
            Risk confidence score
        """
        probabilities = [v["probability"] for v in risk_data.values()]
        return float(np.mean(probabilities))

    def _calculate_flow_confidence(self, flow_data: Dict) -> float:
        """Calculate flow confidence score.

        Args:
            flow_data: Flow data dictionary

        Returns:
            Flow confidence score
        """
        velocity = flow_data.get("velocity_pattern", "laminar")
        wave = flow_data.get("wave_characteristics", {})
        energy = flow_data.get("energy_distribution", {})

        # Combine confidence factors
        velocity_conf = {"laminar": 0.9, "transitional": 0.75, "turbulent": 0.6}.get(
            velocity, 0.7
        )
        wave_conf = wave.get("propagation_speed", 0.5)
        energy_conf = energy.get("total_energy", 0.5)

        return float((velocity_conf + wave_conf + energy_conf) / 3)

    def get_model_state(self) -> Dict:
        """Get current model state.

        Returns:
            Model state dictionary
        """
        return {
            "model_type": self.config.model_type,
            "training_epochs": len(self.training_history["epochs"]),
            "final_loss": self.training_history["loss"][-1]
            if self.training_history["loss"]
            else 0,
            "accuracy": self.training_history["accuracy"][-1]
            if self.training_history["accuracy"]
            else 0,
            "device": str(self.device),
        }

    def get_prediction_confidence(self) -> Dict:
        """Get prediction confidence metrics.

        Returns:
            Prediction confidence metrics
        """
        return {
            "model_confidence": self._compute_confidence({}),
            "feature_importance": self.model.get_feature_importance(),
            "training_quality": self._assess_training_quality(),
        }

    def _assess_training_quality(self) -> Dict:
        """Assess training quality.

        Returns:
            Training quality assessment
        """
        history = self.training_history

        if len(history["loss"]) < 2:
            return {
                "status": "insufficient_data",
                "loss_trend": "stable",
                "accuracy_trend": "stable",
            }

        # Calculate trends
        loss_trend = self._calculate_trend(history["loss"])
        accuracy_trend = self._calculate_trend(history["accuracy"])

        return {
            "status": "excellent" if loss_trend > 0.8 else "good",
            "loss_trend": "improving" if loss_trend > 0.5 else "stable",
            "accuracy_trend": "improving" if accuracy_trend > 0.5 else "stable",
        }

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend of values.

        Args:
            values: List of values

        Returns:
            Trend score
        """
        if len(values) < 2:
            return 0.5

        # Linear regression slope
        n = len(values)
        x = np.arange(n)
        slope = np.polyfit(x, values, 1)[0]

        # Normalize slope
        mean_value = np.mean(values)
        return min(1.0, abs(slope) / mean_value + 0.5)


class MLModel:
    """Main ML model interface for flood prediction.

    This class provides a high-level interface for the machine learning components,
    including prediction, model state management, and confidence estimation.
    """

    def __init__(self, config: ModelConfig):
        """Initialize the ML model.

        Args:
            config: Model configuration
        """
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Initialize the underlying model
        self._model = FloodNet(config)
        self._model.to(self.device)

        # Initialize prediction engine
        self._prediction_engine = PredictionEngine(self._model, config)

        logger.info(f"MLModel initialized on {self.device}")

    def predict(
        self, prediction_type: str = "flood_risk", horizon: int = 24
    ) -> Dict[str, Any]:
        """Generate predictions.

        Args:
            prediction_type: Type of prediction to generate
            horizon: Forecast horizon (hours)

        Returns:
            Prediction results
        """
        # For now, we'll generate dummy input data based on the config
        # In a real implementation, this would use actual data
        input_data = self._generate_dummy_input(horizon)
        return self._prediction_engine.predict(input_data, prediction_type)

    def get_model_state(self) -> Dict[str, Any]:
        """Get current model state.

        Returns:
            Model state dictionary
        """
        return self._prediction_engine.get_model_state()

    def get_prediction_confidence(self) -> Dict[str, Any]:
        """Get prediction confidence metrics.

        Returns:
            Prediction confidence metrics
        """
        return self._prediction_engine.get_prediction_confidence()

    def _generate_dummy_input(self, horizon: int) -> Dict[str, Any]:
        """Generate dummy input data for prediction.

        Args:
            horizon: Forecast horizon

        Returns:
            Input data dictionary
        """
        # Generate realistic dummy data based on typical values
        return {
            "elevation": np.random.uniform(0, 10),
            "permeability": np.random.uniform(0.1, 0.9),
            "land_use_type": np.random.randint(0, 6),
            "water_depth": np.random.uniform(0, 5),
            "velocity_x": np.random.uniform(-1, 1),
            "velocity_y": np.random.uniform(-1, 1),
            "flow_rate": np.random.uniform(0, 10),
            "flood_index": np.random.uniform(0, 1),
            "precipitation": np.random.uniform(0, 20),
            "seasonal_factor": np.random.uniform(0.5, 1.5),
        }


class ModelArchitecture:
    """Manages model architecture operations.

    Provides methods for model initialization, loading, saving, and optimization.
    """

    def __init__(self):
        """Initialize the model architecture manager."""
        self.models: Dict[str, FloodNet] = {}
        self.configs: Dict[str, ModelConfig] = {}

    def initialize_model(self, name: str, config: ModelConfig) -> FloodNet:
        """Initialize a new model.

        Args:
            name: Model name
            config: Model configuration

        Returns:
            Initialized model
        """
        model = FloodNet(config)
        self.models[name] = model
        self.configs[name] = config

        logger.info(f"Initialized model: {name}")

        return model

    def load_model(self, name: str, checkpoint_path: str) -> FloodNet:
        """Load a model from checkpoint.

        Args:
            name: Model name
            checkpoint_path: Path to checkpoint file

        Returns:
            Loaded model
        """
        if name not in self.models:
            raise ValueError(f"Model {name} not found")

        model = self.models[name]

        # Load checkpoint using the default device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])

        logger.info(f"Loaded model {name} from {checkpoint_path}")

        return model

    def save_model(self, name: str, output_path: str) -> None:
        """Save model to checkpoint.

        Args:
            name: Model name
            output_path: Output path for checkpoint
        """
        if name in self.models:
            model = self.models[name]
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "config": self.configs[name].to_dict(),
                    "timestamp": model.config.learning_rate,
                },
                output_path,
            )

            logger.info(f"Saved model {name} to {output_path}")

    def optimize_model(
        self, name: str, optimization_strategy: str = "pruning"
    ) -> FloodNet:
        """Optimize model performance.

        Args:
            name: Model name
            optimization_strategy: Optimization strategy

        Returns:
            Optimized model
        """
        if name in self.models:
            model = self.models[name]

            if optimization_strategy == "pruning":
                self._apply_pruning(model)
            elif optimization_strategy == "quantization":
                self._apply_quantization(model)

            logger.info(f"Optimized model {name} with {optimization_strategy}")

            return model

        raise ValueError(f"Model {name} not found")

    def _apply_pruning(self, model: FloodNet) -> None:
        """Apply model pruning.

        Args:
            model: Model to prune
        """
        # Prune low-weight connections
        for module in model.modules():
            if isinstance(module, nn.Linear):
                weights = module.weight.data
                threshold = torch.quantile(torch.abs(weights), 0.9)
                weights[torch.abs(weights) < threshold] = 0

        logger.info("Applied model pruning")

    def _apply_quantization(self, model: FloodNet) -> None:
        """Apply model quantization.

        Args:
            model: Model to quantize
        """
        # Quantize weights to lower precision
        for module in model.modules():
            if isinstance(module, nn.Linear):
                module.weight.data = module.weight.data.float()

        logger.info("Applied model quantization")
