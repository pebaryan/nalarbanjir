#!/usr/bin/env python3
"""Train FloodNet on synthetic physics simulation data.

This script:
  1. Generates diverse synthetic terrain profiles (flat, valley, hill, basin, channel)
  2. Runs physics simulations with varying water sources and rainfall
  3. Extracts features from each cell at each timestep
  4. Labels cells by flood risk class derived from water depth and Froude number
  5. Trains FloodNet via the TrainingPipeline
  6. Saves a checkpoint to checkpoints/floodnet.pt

Label scheme (5 classes):
  0 - dry (no significant water)
  1 - low  (depth < 0.5 m, subcritical)
  2 - moderate (0.5 <= depth < 1.5 m)
  3 - high (1.5 <= depth < 3.0 m or supercritical)
  4 - severe (depth >= 3.0 m or Froude > 1.0)
"""

import sys
import os
import random
import logging
import numpy as np
import torch
from typing import List, Tuple

# Add project root to path so src/ imports work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.physics.flood_physics_3d import FloodPhysicsEngine3D
from src.ml.model import FloodNet, ModelConfig
from src.ml.training import TrainingPipeline, TrainingConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NUM_SCENARIOS = 40          # number of distinct simulation scenarios
STEPS_PER_SCENARIO = 50   # timesteps per scenario
GRID_SIZE = (30, 30)       # grid dimensions (smaller for speed)
CELL_SIZE = 10.0            # meters per cell
EPOCHS = 20
BATCH_SIZE = 256
LR = 1e-3
CHECKPOINT_DIR = os.path.join(ROOT, "checkpoints")
SEED = 42

np.random.seed(SEED)
random.seed(SEED)
torch.manual_seed(SEED)

# ---------------------------------------------------------------------------
# Terrain generators
# ---------------------------------------------------------------------------

def terrain_flat(n: int) -> np.ndarray:
    """Nearly flat terrain with tiny noise."""
    return np.random.uniform(0, 0.5, (n, n))

def terrain_valley(n: int) -> np.ndarray:
    """U-shaped valley along the center."""
    y = np.arange(n)
    yy, xx = np.meshgrid(y, y, indexing="ij")
    center = n / 2
    return 10 * ((xx - center) ** 2 + (yy - center) ** 2) / (center ** 2) + np.random.uniform(0, 0.3, (n, n))

def terrain_hill(n: int) -> np.ndarray:
    """Raised hill in center, water flows outward."""
    y = np.arange(n)
    yy, xx = np.meshgrid(y, y, indexing="ij")
    center = n / 2
    return 20 * (1 - np.exp(-((xx - center) ** 2 + (yy - center) ** 2) / (2 * (n / 4) ** 2))) + np.random.uniform(0, 0.2, (n, n))

def terrain_basin(n: int) -> np.ndarray:
    """Basin with steep walls."""
    y = np.arange(n)
    yy, xx = np.meshgrid(y, y, indexing="ij")
    center = n / 2
    r = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)
    return 5 * np.maximum(0, r - center * 0.6) + np.random.uniform(0, 0.2, (n, n))

def terrain_channel(n: int) -> np.ndarray:
    """Flat terrain with a channel running diagonally."""
    base = np.ones((n, n)) * 5.0
    y = np.arange(n)
    yy, xx = np.meshgrid(y, y, indexing="ij")
    channel = np.abs((xx - yy) - n / 2) < 4
    base[channel] = 2.0
    return base + np.random.uniform(0, 0.2, (n, n))

def terrain_urban(n: int) -> np.ndarray:
    """Flat with scattered raised buildings."""
    base = np.zeros((n, n))
    for _ in range(15):
        bx, by = np.random.randint(2, n - 2, 2)
        bw, bh = np.random.randint(2, 6, 2)
        base[max(0, bx - bw):min(n, bx + bw), max(0, by - bh):min(n, by + bh)] += np.random.uniform(2, 8)
    return base + np.random.uniform(0, 0.1, (n, n))

TERRAIN_GENERATORS = [
    terrain_flat, terrain_valley, terrain_hill,
    terrain_basin, terrain_channel, terrain_urban
]

# ---------------------------------------------------------------------------
# Feature extraction helpers
# ---------------------------------------------------------------------------

# Land-use types (synthetic): 0=urban, 1=forest, 2=wetland, 3=agriculture, 4=river, 5=coastal
# Permeability correlates with land-use
LANDUSE_PERMEABILITY = {0: 0.1, 1: 0.4, 2: 0.7, 3: 0.5, 4: 0.9, 5: 0.6}

def label_flood_risk(depth: float, froude: float) -> int:
    """Assign flood risk class (0-4) based on depth and Froude number."""
    if depth < 0.01:
        return 0  # dry
    if depth < 0.5 and froude < 0.5:
        return 1  # low
    if depth < 1.5:
        return 2  # moderate
    if froude > 1.0:
        return 4  # severe (supercritical)
    if depth >= 3.0:
        return 4  # severe
    return 3  # high

def extract_features(engine: FloodPhysicsEngine3D, state, elevation, land_use,
                     permeability, rainfall_intensity, seasonal) -> List[Tuple[np.ndarray, int]]:
    """Extract feature-label pairs from simulation state — fully vectorized."""
    depth = state.water_depth
    ux = state.velocity_u
    vy = state.velocity_v
    froude = engine.get_froude_number()
    speed = np.sqrt(ux**2 + vy**2)
    flow_rate = depth * speed
    flood_index = np.clip(depth / 5.0 + speed / 10.0, 0, 1.0)
    # Vectorized labeling
    labels = np.zeros(depth.shape, dtype=np.int64)
    labels[depth >= 0.01] = 1  # default: low
    labels[(depth >= 0.5) & (depth < 1.5)] = 2  # moderate
    labels[(depth >= 1.5) & (depth < 3.0)] = 3  # high
    labels[(depth >= 3.0) | (froude > 1.0)] = 4  # severe
    labels[depth < 0.01] = 0  # dry (override)
    # Build feature array: (N, 10)
    N = engine.nx * engine.ny
    features = np.column_stack([
        elevation.ravel(),
        permeability.ravel(),
        land_use.astype(np.float32).ravel(),
        depth.ravel(),
        ux.ravel(),
        vy.ravel(),
        flow_rate.ravel(),
        flood_index.ravel(),
        rainfall_intensity.ravel(),
        np.full(N, seasonal, dtype=np.float32),
    ]).astype(np.float32)
    return features, labels.ravel()

# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def generate_training_data() -> Tuple[np.ndarray, np.ndarray]:
    """Run many physics scenarios and collect labeled samples."""
    all_features: List[np.ndarray] = []
    all_labels: List[int] = []

    for scenario in range(NUM_SCENARIOS):
        # Pick terrain type
        terrain_fn = TERRAIN_GENERATORS[scenario % len(TERRAIN_GENERATORS)]
        elevation = terrain_fn(GRID_SIZE[0])

        # Generate synthetic land-use map
        land_use = np.random.randint(0, 6, (GRID_SIZE[0], GRID_SIZE[1]))
        permeability = np.zeros((GRID_SIZE[0], GRID_SIZE[1]))
        for lu, perm in LANDUSE_PERMEABILITY.items():
            permeability[land_use == lu] = perm + np.random.uniform(-0.1, 0.1, (land_use == lu).sum())
        permeability = np.clip(permeability, 0, 1)

        # Rainfall (random intensity pattern)
        rainfall_mm_hr = np.random.uniform(0, 50, (GRID_SIZE[0], GRID_SIZE[1]))
        # Convert to m/s for engine
        rainfall_ms = rainfall_mm_hr / 1000.0 / 3600.0

        # Seasonal factor
        seasonal = np.random.uniform(0.5, 1.5)

        # Create engine
        engine = FloodPhysicsEngine3D(grid_size=GRID_SIZE, dx=CELL_SIZE, dy=CELL_SIZE)
        engine.set_terrain(elevation)
        engine.set_rainfall(rainfall_mm_hr)
        engine.set_boundary_conditions("open")

        # Add water source(s)
        num_sources = np.random.randint(1, 4)
        for _ in range(num_sources):
            sx = np.random.randint(5, GRID_SIZE[0] - 5)
            sy = np.random.randint(5, GRID_SIZE[1] - 5)
            depth = np.random.uniform(0.5, 5.0)
            radius = np.random.randint(2, 8)
            engine.add_initial_water_source(sx, sy, depth, radius)

        # Run simulation
        for step in range(STEPS_PER_SCENARIO):
            state = engine.step()
            feats, labs = extract_features(engine, state, elevation, land_use,
                                           permeability, rainfall_mm_hr * seasonal / 3600.0, seasonal)
            all_features.append(feats)
            all_labels.append(labs)
        if (scenario + 1) % 10 == 0:
            logger.info(f"Generated scenario {scenario + 1}/{NUM_SCENARIOS}")

    X = np.concatenate(all_features, axis=0).astype(np.float32)
    y = np.concatenate(all_labels, axis=0).astype(np.int64)

    # Class distribution
    unique, counts = np.unique(y, return_counts=True)
    logger.info("Class distribution:")
    class_names = ["dry", "low", "moderate", "high", "severe"]
    for cls, cnt in zip(unique, counts):
        logger.info(f"  {class_names[cls]} ({cls}): {cnt} ({cnt / len(y) * 100:.1f}%)")

    # Subsample for faster training (still plenty for 300k params)
    MAX_SAMPLES = 500_000
    if len(X) > MAX_SAMPLES:
        indices = np.random.choice(len(X), MAX_SAMPLES, replace=False)
        X = X[indices]
        y = y[indices]
        logger.info(f"Subsampled to {MAX_SAMPLES} samples")

    # Normalize features (standardize)
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-8
    X = (X - mean) / std
    np.save(os.path.join(CHECKPOINT_DIR, "feature_stats.npy"), np.stack([mean, std]))
    logger.info(f"Saved feature normalization stats (mean/std) to {CHECKPOINT_DIR}/feature_stats.npy")

    return X, y

# ---------------------------------------------------------------------------
# Model with cross-entropy (replace softmax + MSE with proper classification head)
# ---------------------------------------------------------------------------

def build_model():
    """Build a wrapper around FloodNet that handles 2D batch input."""
    config = ModelConfig(
        model_type="flood_net",
        input_features=10,
        hidden_dims=[64, 128, 256],
        output_features=5,
        learning_rate=LR,
        dropout_rate=0.1,
        batch_size=BATCH_SIZE,
    )
    import torch.nn as nn

    class FloodNetWrapper(nn.Module):
        """Wraps FloodNet so it accepts (batch, features) and returns (batch, 5)."""
        def __init__(self, inner):
            super().__init__()
            self.inner = inner
        def forward(self, x):
            # x: (batch, features) -> (batch, 1, features)
            out, _ = self.inner(x.unsqueeze(1))
            # out: (batch, 1, 5) -> (batch, 5)
            return out.squeeze(1)

    inner = FloodNet(config)
    # Replace softmax output with linear for cross-entropy compatible training
    inner.output_layer = nn.Linear(config.hidden_dims[-1], config.output_features)
    model = FloodNetWrapper(inner)
    logger.info(f"FloodNet parameters: {sum(p.numel() for p in model.parameters()):,}")
    return model, config

# ---------------------------------------------------------------------------
# Training wrapper (one-hot encode labels for the pipeline)
# ---------------------------------------------------------------------------

def train():
    """Generate data, train, and save checkpoint."""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    logger.info("Generating training data...")
    X, y = generate_training_data()
    logger.info(f"Total samples: {len(X)}, features: {X.shape[1]}")

    logger.info("Building model...")
    model, config = build_model()

    # One-hot encode labels for MSE-based pipeline
    # (The existing TrainingPipeline uses MSE; one-hot makes it work for classification)
    y_onehot = np.zeros((len(y), 5), dtype=np.float32)
    y_onehot[np.arange(len(y)), y] = 1.0

    logger.info(f"Training for {EPOCHS} epochs, batch_size={BATCH_SIZE}, lr={LR}")
    train_config = TrainingConfig(
        learning_rate=LR,
        batch_size=BATCH_SIZE,
        epochs=EPOCHS,
        validation_split=0.15,
        early_stopping_patience=8,
        optimizer_type="adam",
        loss_function="mse",
        metrics=["loss", "mae"],
    )

    pipeline = TrainingPipeline(model, train_config)
    history = pipeline.train(X, y_onehot)

    # Evaluate final accuracy
    model.eval()
    with torch.no_grad():
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.LongTensor(y)
        # Wrapper handles unsqueezing internally
        out = model(X_tensor)
        preds = out.argmax(dim=1)
        accuracy = (preds == y_tensor).float().mean().item()
        logger.info(f"Final accuracy on full dataset: {accuracy * 100:.2f}%")

    # Save checkpoint — save the inner FloodNet model state
    checkpoint_path = os.path.join(CHECKPOINT_DIR, "floodnet.pt")
    torch.save({
        "model_state_dict": model.inner.state_dict(),
        "config": config.to_dict(),
        "history": history,
    }, checkpoint_path)
    logger.info(f"Checkpoint saved to {checkpoint_path}")

    # Save training history
    history_path = os.path.join(CHECKPOINT_DIR, "training_history.json")
    import json
    with open(history_path, "w") as f:
        json.dump({
            "train_loss": history["train_loss"],
            "val_loss": history["val_loss"],
            "accuracy": accuracy,
            "epochs_run": len(history["train_loss"]),
            "total_samples": int(len(X)),
            "config": config.to_dict(),
        }, f, indent=2)
    logger.info(f"Training history saved to {history_path}")

    return checkpoint_path, accuracy

if __name__ == "__main__":
    path, acc = train()
    print(f"\nDone. Checkpoint: {path}")
    print(f"Accuracy: {acc * 100:.2f}%")
