"""Tests for the ML module."""

import numpy as np
import pytest
import torch

try:
    from src.ml.model import (
        MLModel,
        ModelConfig,
        FloodNet,
        FloodAttention,
        PredictionEngine,
        ModelArchitecture,
    )
    from src.ml.training import TrainingPipeline, TrainingConfig
except ImportError:
    # Fallback for when running tests from different directory
    try:
        from ml.model import (
            MLModel,
            ModelConfig,
            FloodNet,
            FloodAttention,
            PredictionEngine,
            ModelArchitecture,
        )
        from ml.training import TrainingPipeline, TrainingConfig
    except ImportError:
        # Final fallback
        import sys

        sys.path.append("src")
        from ml.model import (
            MLModel,
            ModelConfig,
            FloodNet,
            FloodAttention,
            PredictionEngine,
            ModelArchitecture,
        )
        from ml.training import TrainingPipeline, TrainingConfig


class TestModelConfig:
    """Test cases for ModelConfig."""

    def test_default_initialization(self):
        """Test ModelConfig with default values."""
        config = ModelConfig()

        assert config.model_type == "flood_net"
        assert config.input_features == 10
        assert config.hidden_dims == [64, 128, 256]
        assert config.output_features == 5
        assert config.learning_rate == 1e-3
        assert config.dropout_rate == 0.1
        assert config.batch_size == 32

    def test_custom_initialization(self):
        """Test ModelConfig with custom values."""
        config = ModelConfig(
            model_type="custom_net",
            input_features=20,
            hidden_dims=[32, 64, 128],
            output_features=3,
            learning_rate=0.01,
            dropout_rate=0.2,
            batch_size=16,
        )

        assert config.model_type == "custom_net"
        assert config.input_features == 20
        assert config.hidden_dims == [32, 64, 128]
        assert config.output_features == 3
        assert config.learning_rate == 0.01
        assert config.dropout_rate == 0.2
        assert config.batch_size == 16

    def test_from_dict(self):
        """Test creating ModelConfig from dictionary."""
        data = {
            "model_type": "test_net",
            "input_features": 15,
            "hidden_dims": [50, 100],
            "output_features": 8,
            "learning_rate": 0.005,
            "dropout_rate": 0.15,
            "batch_size": 64,
        }
        config = ModelConfig.from_dict(data)

        assert config.model_type == "test_net"
        assert config.input_features == 15
        assert config.hidden_dims == [50, 100]
        assert config.output_features == 8
        assert config.learning_rate == 0.005
        assert config.dropout_rate == 0.15
        assert config.batch_size == 64

    def test_to_dict(self):
        """Test converting ModelConfig to dictionary."""
        config = ModelConfig(
            model_type="dict_test",
            input_features=12,
            hidden_dims=[30, 60, 90],
            output_features=4,
            learning_rate=0.002,
            dropout_rate=0.05,
            batch_size=8,
        )
        data = config.to_dict()

        assert isinstance(data, dict)
        assert data["model_type"] == "dict_test"
        assert data["input_features"] == 12
        assert data["hidden_dims"] == [30, 60, 90]
        assert data["output_features"] == 4
        assert data["learning_rate"] == 0.002
        assert data["dropout_rate"] == 0.05
        assert data["batch_size"] == 8


class TestFloodNet:
    """Test cases for FloodNet."""

    def test_initialization(self):
        """Test FloodNet initialization."""
        config = ModelConfig()
        model = FloodNet(config)

        assert isinstance(model, torch.nn.Module)
        assert model.config == config

        # Check that layers exist
        assert hasattr(model, "input_embedding")
        assert hasattr(model, "hidden_layers")
        assert hasattr(model, "output_layer")
        assert hasattr(model, "attention")

    def test_forward_pass(self):
        """Test forward pass through the network."""
        config = ModelConfig(input_features=5, hidden_dims=[10, 20], output_features=3)
        model = FloodNet(config)
        model.eval()  # Set to eval mode to disable dropout

        # Create test input - add seq_len dimension for attention (batch_size, seq_len, features)
        batch_size = 4
        seq_len = 1
        input_tensor = torch.randn(batch_size, seq_len, config.input_features)

        # Forward pass
        output, attention_weights = model(input_tensor)

        # Check output shape - attention preserves seq_len
        assert output.shape == (batch_size, seq_len, config.output_features)
        # Check that output is a probability distribution (softmax) for each position
        assert torch.allclose(
            output.sum(dim=-1), torch.ones(batch_size, seq_len), atol=1e-5
        )

        # Check attention weights
        assert attention_weights is not None

    def test_get_feature_importance(self):
        """Test getting feature importance."""
        config = ModelConfig(input_features=8)
        model = FloodNet(config)

        importance = model.get_feature_importance()

        assert isinstance(importance, dict)
        assert len(importance) == config.input_features
        for i in range(config.input_features):
            assert f"feature_{i}" in importance
            assert isinstance(importance[f"feature_{i}"], float)
            assert importance[f"feature_{i}"] >= 0


class TestFloodAttention:
    """Test cases for FloodAttention."""

    def test_initialization(self):
        """Test FloodAttention initialization."""
        attention = FloodAttention(embed_dim=64, num_heads=4)

        assert isinstance(attention, torch.nn.Module)
        assert attention.embed_dim == 64
        assert attention.num_heads == 4

    def test_forward_pass(self):
        """Test forward pass through attention module."""
        attention = FloodAttention(embed_dim=64, num_heads=4)
        attention.train(False)  # Set to eval mode to disable dropout

        # Create test input: (batch_size, seq_len, embed_dim)
        batch_size = 2
        seq_len = 5
        embed_dim = 64
        input_tensor = torch.randn(batch_size, seq_len, embed_dim)

        # Forward pass
        output, attention_weights = attention(input_tensor)

        # Check output shape
        assert output.shape == (batch_size, seq_len, embed_dim)

        # Check attention weights shape
        assert attention_weights.shape == (batch_size, 4, seq_len, seq_len)

        # Check that attention weights sum to 1 across the last dimension
        # Note: Dropout is disabled in eval mode, so sums should be close to 1
        assert torch.allclose(
            attention_weights.sum(dim=-1), torch.ones(batch_size, 4, seq_len), atol=1e-5
        )


class TestMLModel:
    """Test cases for MLModel."""

    def test_initialization(self):
        """Test MLModel initialization."""
        config = ModelConfig()
        model = MLModel(config)

        assert isinstance(model, MLModel)
        assert model.config == config
        assert hasattr(model, "_model")
        assert hasattr(model, "_prediction_engine")

    def test_predict(self):
        """Test prediction generation."""
        config = ModelConfig()
        model = MLModel(config)

        # Test prediction generation
        predictions = model.predict(prediction_type="flood_risk", horizon=24)

        assert isinstance(predictions, dict)
        # Should have some prediction data
        assert len(predictions) > 0

    def test_get_model_state(self):
        """Test getting model state."""
        config = ModelConfig()
        model = MLModel(config)

        state = model.get_model_state()

        assert isinstance(state, dict)
        assert "model_type" in state
        assert "training_epochs" in state
        assert "final_loss" in state
        assert "accuracy" in state
        assert "device" in state

    def test_get_prediction_confidence(self):
        """Test getting prediction confidence."""
        config = ModelConfig()
        model = MLModel(config)

        confidence = model.get_prediction_confidence()

        assert isinstance(confidence, dict)


class TestPredictionEngine:
    """Test cases for PredictionEngine."""

    def test_initialization(self):
        """Test PredictionEngine initialization."""
        config = ModelConfig()
        model = FloodNet(config)
        engine = PredictionEngine(model, config)

        assert engine.model == model
        assert engine.config == config
        assert hasattr(engine, "device")

    def test_prepare_input(self):
        """Test input preparation."""
        config = ModelConfig()
        model = FloodNet(config)
        engine = PredictionEngine(model, config)

        input_data = {
            "elevation": 100.0,
            "permeability": 0.5,
            "land_use_type": 2,
            "water_depth": 1.5,
            "velocity_x": 0.2,
            "velocity_y": 0.1,
            "flow_rate": 1.0,
            "flood_index": 0.3,
            "precipitation": 0.0,
            "seasonal_factor": 1.0,
        }

        tensor_input = engine._prepare_input(input_data)

        assert isinstance(tensor_input, torch.Tensor)
        # Shape should be (batch=1, seq_len=1, features) for attention mechanism
        assert tensor_input.shape == (1, 1, config.input_features)
        assert tensor_input.dtype == torch.float32

    def test_extract_flood_risk(self):
        """Test flood risk extraction."""
        config = ModelConfig(input_features=10, output_features=4)
        model = FloodNet(config)
        engine = PredictionEngine(model, config)

        # Create mock output tensor
        output = torch.tensor([[0.1, 0.2, 0.4, 0.3]])  # Probabilities for 4 risk levels

        predictions = engine._extract_flood_risk(output)

        assert isinstance(predictions, dict)
        assert "low" in predictions
        assert "moderate" in predictions
        assert "high" in predictions
        assert "severe" in predictions

        # Check structure
        for level in ["low", "moderate", "high", "severe"]:
            assert "probability" in predictions[level]
            assert "threshold" in predictions[level]
            assert isinstance(predictions[level]["probability"], float)
            assert isinstance(predictions[level]["threshold"], float)

        # Check values (with tolerance for floating point)
        assert abs(predictions["low"]["probability"] - 0.1) < 1e-6
        assert abs(predictions["moderate"]["probability"] - 0.2) < 1e-6
        assert abs(predictions["high"]["probability"] - 0.4) < 1e-6
        assert abs(predictions["severe"]["probability"] - 0.3) < 1e-6

    def test_get_model_state(self):
        """Test getting model state."""
        config = ModelConfig()
        model = FloodNet(config)
        engine = PredictionEngine(model, config)

        state = engine.get_model_state()

        assert isinstance(state, dict)
        assert "model_type" in state
        assert "training_epochs" in state
        assert "final_loss" in state
        assert "accuracy" in state
        assert "device" in state

        assert state["model_type"] == config.model_type
        assert state["training_epochs"] == 0
        assert isinstance(state["device"], str)


class TestModelArchitecture:
    """Test cases for ModelArchitecture."""

    def test_initialization(self):
        """Test ModelArchitecture initialization."""
        arch = ModelArchitecture()

        assert isinstance(arch, ModelArchitecture)
        assert isinstance(arch.models, dict)
        assert isinstance(arch.configs, dict)
        assert len(arch.models) == 0
        assert len(arch.configs) == 0

    def test_initialize_model(self):
        """Test model initialization."""
        arch = ModelArchitecture()
        config = ModelConfig(
            model_type="test_model", input_features=8, output_features=4
        )

        model = arch.initialize_model("test_model", config)

        assert isinstance(model, FloodNet)
        assert "test_model" in arch.models
        assert "test_model" in arch.configs
        assert arch.models["test_model"] == model
        assert arch.configs["test_model"] == config

    def test_load_model_not_implemented(self):
        """Test that load_model raises ValueError (since we're not testing actual file I/O)."""
        arch = ModelArchitecture()

        with pytest.raises(ValueError, match="Model nonexistent not found"):
            arch.load_model("nonexistent", "/fake/path/to/model.pt")


class TestTrainingPipeline:
    """Test cases for TrainingPipeline."""

    def test_initialization(self):
        """Test TrainingPipeline initialization."""
        config = ModelConfig()
        model = FloodNet(config)
        training_config = TrainingConfig()
        pipeline = TrainingPipeline(model, training_config)

        assert isinstance(pipeline, TrainingPipeline)
        assert pipeline.model == model
        assert pipeline.config == training_config
        assert hasattr(pipeline, "optimizer")
        assert hasattr(pipeline, "criterion")
        assert hasattr(pipeline, "history")

    def test_prepare_data(self):
        """Test data preparation."""
        config = ModelConfig()
        model = FloodNet(config)
        training_config = TrainingConfig()
        pipeline = TrainingPipeline(model, training_config)

        # Create test data
        X = np.random.rand(100, 10)
        y = np.random.rand(100, 1)

        train_loader, val_loader = pipeline.prepare_data(X, y)

        # Check that we got data loaders
        assert hasattr(train_loader, "__iter__")
        assert hasattr(val_loader, "__iter__")


if __name__ == "__main__":
    pytest.main([__file__])
