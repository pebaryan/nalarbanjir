"""Training pipeline for ML models in Flood Prediction World Model.

This module provides training capabilities for the machine learning components
including optimization, validation, and model persistence.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from typing import Dict, List, Any, Optional
import numpy as np
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)


class TrainingConfig:
    """Configuration for training process.

    Attributes:
        learning_rate: Learning rate for optimizer
        batch_size: Batch size for training
        epochs: Number of training epochs
        validation_split: Fraction of data to use for validation
        early_stopping_patience: Patience for early stopping
        optimizer_type: Type of optimizer to use
        loss_function: Loss function to use
        metrics: List of metrics to track
    """

    def __init__(
        self,
        learning_rate: float = 0.001,
        batch_size: int = 32,
        epochs: int = 100,
        validation_split: float = 0.2,
        early_stopping_patience: int = 10,
        optimizer_type: str = "adam",
        loss_function: str = "mse",
        metrics: Optional[List[str]] = None,
    ):
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.validation_split = validation_split
        self.early_stopping_patience = early_stopping_patience
        self.optimizer_type = optimizer_type
        self.loss_function = loss_function
        self.metrics = metrics or ["loss", "mae"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "validation_split": self.validation_split,
            "early_stopping_patience": self.early_stopping_patience,
            "optimizer_type": self.optimizer_type,
            "loss_function": self.loss_function,
            "metrics": self.metrics,
        }


class TrainingPipeline:
    """Pipeline for training ML models.

    Handles the complete training process including data preparation,
    model optimization, validation, and checkpointing.
    """

    def __init__(self, model: torch.nn.Module, config: TrainingConfig):
        """Initialize the training pipeline.

        Args:
            model: PyTorch model to train
            config: Training configuration
        """
        self.model = model
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        # Initialize optimizer
        self.optimizer = self._create_optimizer()

        # Initialize loss function
        self.criterion = self._create_loss_function()

        # Training history
        self.history = {"train_loss": [], "val_loss": [], "learning_rate": []}

        logger.info(f"TrainingPipeline initialized on {self.device}")

    def _create_optimizer(self) -> torch.optim.Optimizer:
        """Create optimizer based on configuration."""
        if self.config.optimizer_type.lower() == "adam":
            return optim.Adam(self.model.parameters(), lr=self.config.learning_rate)
        elif self.config.optimizer_type.lower() == "sgd":
            return optim.SGD(
                self.model.parameters(), lr=self.config.learning_rate, momentum=0.9
            )
        elif self.config.optimizer_type.lower() == "rmsprop":
            return optim.RMSprop(self.model.parameters(), lr=self.config.learning_rate)
        else:
            # Default to Adam
            return optim.Adam(self.model.parameters(), lr=self.config.learning_rate)

    def _create_loss_function(self) -> nn.Module:
        """Create loss function based on configuration."""
        if self.config.loss_function.lower() == "mse":
            return nn.MSELoss()
        elif self.config.loss_function.lower() == "mae":
            return nn.L1Loss()
        elif self.config.loss_function.lower() == "cross_entropy":
            return nn.CrossEntropyLoss()
        elif self.config.loss_function.lower() == "bce":
            return nn.BCELoss()
        else:
            # Default to MSE
            return nn.MSELoss()

    def prepare_data(self, X: np.ndarray, y: np.ndarray) -> tuple:
        """Prepare data for training.

        Args:
            X: Input features
            y: Target values

        Returns:
            Tuple of (train_loader, val_loader) as PyTorch DataLoaders
        """
        from torch.utils.data import TensorDataset, DataLoader, random_split

        # Convert to tensors
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y)

        # Create dataset
        dataset = TensorDataset(X_tensor, y_tensor)

        # Split into train and validation
        val_size = int(len(dataset) * self.config.validation_split)
        train_size = len(dataset) - val_size
        train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

        # Create data loaders
        train_loader = DataLoader(
            train_dataset, batch_size=self.config.batch_size, shuffle=True
        )
        val_loader = DataLoader(val_dataset, batch_size=self.config.batch_size)

        return train_loader, val_loader

    def train_epoch(self, train_loader) -> float:
        """Train for one epoch.

        Args:
            train_loader: DataLoader for training data

        Returns:
            Average training loss for the epoch
        """
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(self.device)
            batch_y = batch_y.to(self.device)

            # Zero gradients
            self.optimizer.zero_grad()

            # Forward pass
            outputs = self.model(batch_X)
            if isinstance(outputs, tuple):
                outputs = outputs[0]  # Handle models that return tuples

            # Calculate loss
            loss = self.criterion(outputs, batch_y)

            # Backward pass
            loss.backward()

            # Optimize
            self.optimizer.step()

            total_loss += loss.item()
            num_batches += 1

        return total_loss / max(num_batches, 1)

    def validate(self, val_loader) -> float:
        """Validate the model.

        Args:
            val_loader: DataLoader for validation data

        Returns:
            Average validation loss
        """
        self.model.eval()
        total_loss = 0.0
        num_batches = 0

        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)

                outputs = self.model(batch_X)
                if isinstance(outputs, tuple):
                    outputs = outputs[0]

                loss = self.criterion(outputs, batch_y)
                total_loss += loss.item()
                num_batches += 1

        return total_loss / max(num_batches, 1)

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, List[float]]:
        """Train the model.

        Args:
            X: Input features
            y: Target values

        Returns:
            Training history dictionary
        """
        # Prepare data
        train_loader, val_loader = self.prepare_data(X, y)

        # Training loop
        best_val_loss = float("inf")
        patience_counter = 0

        logger.info(f"Starting training for {self.config.epochs} epochs")

        for epoch in range(self.config.epochs):
            # Train
            train_loss = self.train_epoch(train_loader)

            # Validate
            val_loss = self.validate(val_loader)

            # Record history
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["learning_rate"].append(self.optimizer.param_groups[0]["lr"])

            # Log progress
            if (epoch + 1) % 10 == 0 or epoch == 0:
                logger.info(
                    f"Epoch [{epoch + 1}/{self.config.epochs}] "
                    f"Train Loss: {train_loss:.6f}, "
                    f"Val Loss: {val_loss:.6f}"
                )

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model (in a real implementation)
            else:
                patience_counter += 1

            if patience_counter >= self.config.early_stopping_patience:
                logger.info(f"Early stopping triggered at epoch {epoch + 1}")
                break

        logger.info("Training completed")
        return self.history

    def save_checkpoint(self, filepath: str) -> None:
        """Save model checkpoint.

        Args:
            filepath: Path to save checkpoint
        """
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "config": self.config.to_dict(),
                "history": self.history,
            },
            filepath,
        )
        logger.info(f"Checkpoint saved to {filepath}")

    def load_checkpoint(self, filepath: str) -> None:
        """Load model checkpoint.

        Args:
            filepath: Path to load checkpoint from
        """
        checkpoint = torch.load(filepath, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.history = checkpoint["history"]
        logger.info(f"Checkpoint loaded from {filepath}")


# Factory function for easy pipeline creation
def create_training_pipeline(
    model: torch.nn.Module,
    learning_rate: float = 0.001,
    batch_size: int = 32,
    epochs: int = 100,
) -> TrainingPipeline:
    """Create a training pipeline with default settings.

    Args:
        model: PyTorch model to train
        learning_rate: Learning rate for training
        batch_size: Batch size for training
        epochs: Number of training epochs

    Returns:
        Configured TrainingPipeline instance
    """
    config = TrainingConfig(
        learning_rate=learning_rate, batch_size=batch_size, epochs=epochs
    )
    return TrainingPipeline(model, config)
