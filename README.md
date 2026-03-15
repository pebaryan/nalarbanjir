# Flood Prediction World Model

A teaching instrument combining hydrodynamic physics (shallow water wave equations) with machine learning for flood prediction and visualization.

## Overview

This project develops a **world model** that simulates flood dynamics using:
- **Physics-based**: Shallow water wave equations governing water flow
- **Machine Learning**: Data-driven predictions and pattern recognition
- **Visualization**: Interactive rendering of flood dynamics

## Core Concepts

### 1. Shallow Water Equations

The system is governed by the 2D shallow water wave equations:

```
∂h/∂t + ∂(hu)/∂x + ∂(hv)/∂y = 0  (Continuity)
∂(hu)/∂t + ∂(hu²)/∂x + ∂(huv)/∂y = -gh∂η/∂x + friction  (Momentum x)
∂(hv)/∂t + ∂(huv)/∂x + ∂(hv²)/∂y = -gh∂η/∂y + friction  (Momentum y)
```

Where:
- h = water depth
- u, v = velocity components
- η = water surface elevation
- g = gravitational acceleration

### 2. World Model Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FLOOD WORLD MODEL                     │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   PHYSICS    │  │    ML        │  │  VISUALIZATION│   │
│  │   ENGINE     │  │   MODEL      │  │   RENDERER   │   │
│  │              │  │              │  │              │   │
│  │ - Wave Eq.   │  │ - Pattern    │  │ - Water      │   │
│  │   Solver     │  │   Detection  │  │   Surface    │   │
│  │ - Flow       │  │ - Anomaly    │  │ - Flow       │   │
│  │   Dynamics   │  │   Detection  │  │   Vectors    │   │
│  │ - Terrain    │  │ - Forecast   │  │ - Flood      │   │
│  │   Interaction│  │   Models     │  │   Zones      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│                     ↓  ↓  ↓                              │
│              ┌────────────────────────┐                 │
│              │   DATA PIPELINE        │                 │
│              │   - Sensing            │                 │
│              │   - Processing         │                 │
│              │   - Integration        │                 │
│              └────────────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
flood-prediction-world/
├── src/
│   ├── physics/
│   │   ├── shallow_water.py       # Shallow water equation solver
│   │   ├── terrain.py             # Terrain modeling
│   │   └── boundary_conditions.py # Boundary conditions
│   ├── ml/
│   │   ├── model.py               # ML model architecture
│   │   ├── training.py            # Training pipeline
│   │   └── prediction.py          # Prediction module
│   ├── visualization/
│   │   ├── renderer.py            # Visualization renderer
│   │   ├── water_surface.py       # Water surface visualization
│   │   └── flow_vectors.py        # Flow vector visualization
│   └── world/
│       ├── world_state.py         # World state management
│       └── simulator.py           # Simulation engine
├── notebooks/
│   └── exploration.ipynb          # Jupyter notebook for exploration
├── config/
│   └── model_config.yaml           # Configuration file
├── data/
│   ├── terrain/                   # Terrain data
│   └── observations/               # Observation data
└── scripts/
    ├── run_simulation.py          # Run simulation
    └── generate_demo.py            # Generate demo data
```

## Quick Start

### Installation

```bash
cd flood-prediction-world
pip install -r requirements.txt
```

### Running the Simulation

```bash
# Run full simulation with visualization
python scripts/run_simulation.py --config config/model_config.yaml
```

### Key Features

1. **Physics-Based Simulation**
   - Shallow water wave equation solver
   - Terrain interaction
   - Boundary condition handling

2. **Machine Learning Integration**
   - Pattern detection in water flow
   - Anomaly identification
   - Forecast models

3. **Interactive Visualization**
   - Water surface rendering
   - Flow vector fields
   - Flood zone mapping

## Teaching Applications

This world model serves as an educational tool for:
- Understanding hydrodynamic principles
- Exploring ML applications in environmental modeling
- Visualizing complex fluid dynamics
- Demonstrating simulation-to-deployment pipelines

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development guidelines.
# nalarbanjir
