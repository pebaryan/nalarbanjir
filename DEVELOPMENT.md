# Flood Prediction World Model - Development Guide

## Overview

This development guide provides comprehensive documentation for the Flood Prediction World Model project, covering architecture, development workflows, best practices, and deployment strategies.

## Architecture

### System Architecture

The system follows a ComfyUI-like architecture with a web-based frontend and a backend for heavy computation:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │           Web Browser (Nginx Static Server)               ││
│  │  - HTML/CSS/JavaScript UI                                 ││
│  │  - Real-time Visualization                               ││
│  │  - Interactive Dashboard                                 ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API GATEWAY                                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Nginx Reverse Proxy                         ││
│  │  - Load Balancing                                        ││
│  │  - SSL Termination                                       ││
│  │  - WebSocket Support                                     ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              │ API Calls
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │           FastAPI Backend Server                         ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   ││
│  │  │   Physics    │  │     ML       │  │   Data       │   ││
│  │  │   Engine     │  │   Service    │  │   Pipeline   │   ││
│  │  │              │  │              │  │              │   ││
│  │  │ - Shallow    │  │ - Model      │  │ - Data       │   ││
│  │  │   Water      │  │   Training   │  │   Loading    │   ││
│  │  │   Equations  │  │   Inference  │  │   Processing │   ││
│  │  │ - Wave       │  │ - Prediction │  │ - Caching    │   ││
│  │  │   Propagation│  │              │  │              │   ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Database/Storage
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Physics    │  │   ML Models  │  │  Static      │        │
│  │   Data       │  │   Store      │  │  Assets      │        │
│  │              │  │              │  │              │        │
│  │ - Simulation │  │ - Trained    │  │ - Frontend   │        │
│  │   Results    │  │   Models     │  │   Files      │        │
│  │ - Terrain    │  │ - Predictions│  │ - Styles     │        │
│  │   Data       │  │              │  │              │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

#### 1. Physics Engine

The physics engine implements the shallow water wave equations:

**Core Components:**
- ShallowWaterSolver: Governs water dynamics
- WavePropagationAnalyzer: Analyzes wave characteristics
- BoundaryConditions: Manages domain boundaries

**Key Equations:**
```
Continuity: ∂h/∂t + ∂(hu)/∂x + ∑(hv)/∂y = 0

Momentum X: ∂(hu)/∂t + ∂(hu²)/∂x + ∂(huv)/∂y = -gh∂η/∂x + friction

Momentum Y: ∂(hv)/∂t + ∂(huv)/∂x + ∂(hv²)/∂y = -gh∂η/∂y + friction
```

#### 2. Machine Learning Service

The ML service provides intelligent predictions and analysis:

**Core Components:**
- ModelArchitecture: Neural network structure
- PredictionEngine: Real-time prediction
- TrainingPipeline: Model training and optimization

**Model Types:**
- FloodNet: Main prediction network
- FloodAttention: Attention mechanism
- PredictionEngine: Forecasting capabilities

#### 3. Visualization Renderer

The visualization renderer provides interactive displays:

**Core Components:**
- WaterSurfaceRenderer: Water surface visualization
- FlowVectorRenderer: Flow dynamics display
- FloodZoneMapper: Risk zone mapping

#### 4. Data Management

Comprehensive data management for the system:

**Data Flow:**
1. Data Collection → 2. Processing → 3. Storage → 4. Analysis

**Data Sources:**
- Simulation data
- Terrain information
- ML predictions
- User interactions

## Development Workflow

### Project Structure

```
flood-prediction-world/
├── config/                          # Configuration files
│   └── model_config.yaml           # Main configuration
│
├── frontend/                        # Web interface
│   ├── static/                     # Static assets
│   │   ├── css/                    # Stylesheets
│   │   │   ├── styles.css          # Main styles
│   │   │   └── visualization.css   # Visualization styles
│   │   └── js/                     # JavaScript modules
│   │       ├── app.js              # Core application
│   │       ├── visualization.js    # Visualization logic
│   │       ├── simulation.js       # Simulation controls
│   │       └── analytics.js        # Analytics features
│   └── templates/                   # HTML templates
│       └── index.html              # Main interface
│
├── src/                            # Source code
│   ├── physics/                    # Physics engine
│   │   ├── shallow_water.py        # Water equations
│   │   ├── terrain.py              # Terrain modeling
│   │   └── boundary_conditions.py  # Boundary management
│   │
│   ├── ml/                         # Machine learning
│   │   ├── model.py                # Model architecture
│   │   ├── training.py             # Training pipeline
│   │   └── prediction.py           # Prediction engine
│   │
│   ├── visualization/              # Visualization
│   │   ├── renderer.py             # Main renderer
│   │   ├── water_surface.py        # Water visualization
│   │   └── flow_vectors.py         # Flow visualization
│   │
│   └── server.py                   # FastAPI server
│
├── scripts/                        # Utility scripts
│   ├── run_simulation.py           # Simulation runner
│   └── deploy.sh                   # Deployment script
│
├── tests/                          # Test suite
│   ├── test_physics.py             # Physics tests
│   ├── test_ml.py                  # ML tests
│   └── test_integration.py         # Integration tests
│
├── docker-compose.yml              # Docker orchestration
├── Dockerfile                      # Container definition
├── requirements.txt                # Python dependencies
└── README.md                       # Project documentation
```

### Development Environment Setup

#### Prerequisites

```bash
# Required software
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+
- Node.js 18+ (for frontend development)
```

#### Local Development

1. **Clone Repository**
```bash
git clone https://github.com/your-org/flood-prediction-world.git
cd flood-prediction-world
```

2. **Setup Virtual Environment**
```bash
python -m venv .venv
source .venv/bin/activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Run Development Server**
```bash
python scripts/run_simulation.py --serve
```

### Code Standards

#### Python Development

**Coding Style:**
- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Implement comprehensive docstrings
- Write modular and reusable code

**Example:**
```python
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class WaterState:
    """Represents the state of water at a given time."""
    
    elevation: np.ndarray
    velocity_x: np.ndarray
    velocity_y: np.ndarray
    depth: np.ndarray
    time: float

def process_water_state(
    state: WaterState,
    config: Dict
) -> Dict:
    """Process water state and return analysis results.
    
    Args:
        state: Current water state
        config: Configuration parameters
        
    Returns:
        Analysis results dictionary
    """
    # Implementation details
    ...
```

#### JavaScript Development

**Module Structure:**
```javascript
// Application module
class Application {
    constructor(config) {
        this.config = config;
        this.state = this.initializeState();
    }
    
    async initialize() {
        await this.loadComponents();
        this.attachEventListeners();
    }
}

export default Application;
```

#### Testing

**Test Strategy:**
- Unit tests for individual components
- Integration tests for component interactions
- End-to-end tests for complete workflows
- Performance tests for system capabilities

**Example Test:**
```python
import pytest
from src.physics.shallow_water import ShallowWaterSolver

class TestShallowWaterSolver:
    
    def test_initialization(self):
        """Test solver initialization."""
        solver = ShallowWaterSolver(
            config={'gravity': 9.81},
            grid_resolution=(100, 100)
        )
        assert solver.nx == 100
        assert solver.ny == 100
    
    def test_evolution(self):
        """Test state evolution over time."""
        solver = ShallowWaterSolver(
            config={'time_step': 1.0},
            grid_resolution=(50, 50)
        )
        states = solver.evolve(steps=100)
        assert len(states) == 101
        assert states[-1].time > states[0].time
```

### API Development

#### REST API Design

**Endpoints:**
```
GET  /api/state              - Get system state
POST /api/simulate           - Run simulation
GET  /api/terrain            - Get terrain data
POST /api/predict            - Make predictions
GET  /api/history            - Get historical data
WS   /ws                     - WebSocket connection
```

**Request/Response Format:**
```json
{
    "simulation": {
        "total_steps": 1000,
        "final_time": 3600.0,
        "wave_propagation": {...}
    },
    "flood_zones": {
        "low_risk": [...],
        "moderate_risk": [...],
        "high_risk": [...],
        "severe_risk": [...]
    },
    "output": {...}
}
```

#### WebSocket Communication

**Message Types:**
```json
{
    "type": "simulation_control",
    "command": "start",
    "timestamp": 1640000000000
}
```

### Deployment

#### Docker Containerization

**Dockerfile Best Practices:**
- Multi-stage builds for optimization
- Minimal base images
- Health checks for container monitoring
- Environment variable configuration

**Docker Compose Setup:**
```yaml
services:
  flood-world:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
  
  frontend:
    image: nginx:alpine
    ports:
      - "80:80"
    depends_on:
      - flood-world
```

#### CI/CD Pipeline

**GitHub Actions Workflow:**
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build and push Docker image
        run: |
          docker build -t flood-world:latest .
          docker push flood-world:latest
```

### Monitoring and Maintenance

#### Health Monitoring

**Key Metrics:**
- System performance (CPU, memory, network)
- Application health (API response times, error rates)
- Business metrics (flood risk levels, prediction accuracy)

**Alerting:**
```python
# Define alert thresholds
ALERT_THRESHOLDS = {
    'response_time': 500,  # milliseconds
    'error_rate': 0.05,    # percentage
    'flood_risk': 0.75     # risk index
}
```

#### Logging Strategy

**Log Levels:**
- DEBUG: Detailed diagnostic information
- INFO: General operational messages
- WARNING: Potential issues requiring attention
- ERROR: Errors requiring immediate attention
- CRITICAL: Critical errors impacting operations

**Log Format:**
```
[2024-01-15 10:30:45] INFO - PhysicsEngine - Simulation started
[2024-01-15 10:30:46] DEBUG - MLService - Model loaded successfully
[2024-01-15 10:30:47] INFO - Visualization - Real-time rendering enabled
```

### Performance Optimization

#### Code Optimization

**Techniques:**
- Efficient data structures
- Caching strategies
- Lazy loading
- Asynchronous processing

**Performance Metrics:**
- Response times
- Throughput
- Resource utilization
- Scalability

#### Database Optimization

**Strategies:**
- Index optimization
- Query optimization
- Data partitioning
- Backup and recovery

## Contributing

### Development Guidelines

1. **Code Quality:**
   - Write clean, maintainable code
   - Implement comprehensive documentation
   - Follow coding standards

2. **Testing:**
   - Maintain high test coverage
   - Perform regular regression testing
   - Monitor performance metrics

3. **Documentation:**
   - Keep documentation up-to-date
   - Document API endpoints
   - Provide user guides

### Release Process

**Versioning:**
- Semantic versioning (MAJOR.MINOR.PATCH)
- Clear release notes
- Change log maintenance

**Release Checklist:**
- [ ] Code review completed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Performance validated
- [ ] Deployment verified

## Troubleshooting

### Common Issues

**1. Container Startup Issues**
```bash
# Check container logs
docker logs flood-world-flood-world

# Verify container health
docker inspect flood-world-flood-world
```

**2. Performance Optimization**
```bash
# Monitor resource usage
docker stats flood-world-flood-world

# Analyze network performance
docker exec flood-world-flood-world netstat -tuln
```

**3. Data Management**
```bash
# Backup data volumes
docker run --rm -v flood-data:/data tar czf backup.tar.gz /data

# Restore from backup
docker run --rm -v flood-data:/data -v $(pwd):/backup tar xzf /backup/backup.tar.gz -C /data
```

## Resources

### Documentation

- [API Reference](docs/api-reference.md)
- [Configuration Guide](docs/configuration-guide.md)
- [User Manual](docs/user-manual.md)

### External Resources

- [Shallow Water Equations](https://en.wikipedia.org/wiki/Shallow_water_equations)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Best Practices](https://docs.docker.com/develop/develop-best-practices/)

---

For support and inquiries, please contact the development team or visit the project repository.
