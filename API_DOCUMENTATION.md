# API Documentation - Flood Prediction World Model

## Overview

The Flood Prediction World Model provides a REST API and WebSocket endpoints for running flood simulations, managing terrain models, generating ML predictions, and visualizing results.

**Base URL:** `http://localhost:8000` (Local) or `http://192.168.0.14:8000` (Remote)

**WebSocket URL:** `ws://192.168.0.14:8000/ws`

## Quick Start

The server is currently running and accessible at:
- **Local**: http://localhost:8000
- **Remote**: http://192.168.0.14:8000
- **Health Check**: http://192.168.0.14:8000/health

## REST API Endpoints

### Health Check

#### GET /health
Check the health status of the API and its components.

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "physics_engine": "healthy",
    "ml_model": "healthy",
    "visualization": "healthy"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Simulation

#### POST /api/v1/simulation/run
Run a flood simulation with specified parameters.

**Request Body:**
```json
{
  "steps": 100,
  "output_format": "full",
  "config": {
    "gravity": 9.81,
    "time_step": 1.0,
    "grid_resolution": [100, 100]
  }
}
```

**Parameters:**
- `steps` (integer): Number of simulation steps (default: 100)
- `output_format` (string): Output detail level - "full", "compact", or "streaming"
- `config` (object): Physics simulation configuration (optional)

**Response:**
```json
{
  "status": "success",
  "simulation": {
    "total_steps": 100,
    "final_time": 100.0,
    "wave_propagation": {
      "celerity": 4.429,
      "kinetic_energy": 0.5,
      "potential_energy": 19.62
    }
  },
  "flood_zones": {
    "low_risk": [],
    "moderate_risk": [],
    "high_risk": [],
    "severe_risk": []
  },
  "output": {
    "visualization": {
      "water_surface": {...},
      "flow_vectors": {...},
      "flood_zones": {...}
    }
  }
}
```

#### GET /api/v1/simulation/state
Get the current simulation state.

**Response:**
```json
{
  "physics": {
    "time": 50.0,
    "grid_resolution": {"nx": 100, "ny": 100},
    "state": {
      "elevation": [...],
      "velocity_x": [...],
      "velocity_y": [...],
      "depth": [...]
    }
  },
  "terrain": {
    "elevation": {...},
    "land_use": {...},
    "permeability": {...}
  },
  "ml": {
    "model_type": "flood_net",
    "training_epochs": 0,
    "device": "cpu"
  }
}
```

### Terrain

#### GET /api/v1/terrain/data
Get terrain data for visualization.

**Response:**
```json
{
  "elevation": {
    "min": 0.0,
    "max": 10.5,
    "mean": 5.2,
    "data": [[...]]
  },
  "land_use": {
    "classification": [[...]],
    "types": ["water", "urban", "agricultural", "forest", "wetland", "open_land"]
  },
  "permeability": {
    "min": 0.1,
    "max": 0.8,
    "mean": 0.45,
    "data": [[...]]
  },
  "flood_thresholds": {
    "minor": 1.0,
    "moderate": 2.0,
    "major": 3.0,
    "severe": 5.0
  }
}
```

#### POST /api/v1/terrain/flood-zones
Identify flood zones based on water depth.

**Request Body:**
```json
{
  "water_depth": [[...]]
}
```

**Response:**
```json
{
  "low_risk": [[0, 0], [0, 1]],
  "moderate_risk": [[1, 2]],
  "high_risk": [[2, 3]],
  "severe_risk": []
}
```

### Predictions

#### POST /api/v1/predictions/make
Generate ML predictions for flood risk.

**Request Body:**
```json
{
  "prediction_type": "flood_risk",
  "horizon": 24,
  "input_data": {
    "elevation": 5.0,
    "permeability": 0.5,
    "water_depth": 2.5,
    "velocity_x": 0.3,
    "velocity_y": 0.1
  }
}
```

**Parameters:**
- `prediction_type` (string): Type of prediction - "flood_risk", "flow_dynamics", "water_quality", "comprehensive"
- `horizon` (integer): Forecast horizon in hours (default: 24)
- `input_data` (object): Input features for prediction

**Response:**
```json
{
  "flood_risk": {
    "low": {"probability": 0.1, "threshold": 0.25},
    "moderate": {"probability": 0.3, "threshold": 0.5},
    "high": {"probability": 0.4, "threshold": 0.75},
    "severe": {"probability": 0.2, "threshold": 1.0}
  },
  "confidence": {
    "overall": 0.85,
    "flood_risk": 0.82,
    "flow_dynamics": 0.88
  },
  "metadata": {
    "prediction_type": "flood_risk",
    "timestamp": "2024-01-15T10:30:00Z",
    "model_type": "flood_net"
  }
}
```

#### GET /api/v1/predictions/confidence
Get prediction confidence metrics.

**Response:**
```json
{
  "confidence_scores": {
    "flood_risk": 0.82,
    "flow_velocity": 0.88,
    "water_depth": 0.85
  },
  "uncertainty_bounds": {
    "flood_risk": {"lower": 0.15, "upper": 0.95},
    "flow_velocity": {"lower": 0.25, "upper": 0.90}
  }
}
```

### Visualization

#### POST /api/v1/visualization/render
Render visualization data.

**Request Body:**
```json
{
  "output_format": "full",
  "layers": ["water_surface", "flow_vectors", "flood_zones"]
}
```

**Response:**
```json
{
  "visualization": {
    "water_surface": {
      "type": "water_surface",
      "data": [[...]],
      "color": "#3b82f6",
      "min_depth": 0.0,
      "max_depth": 5.0
    },
    "flow_vectors": {
      "type": "flow_vectors",
      "vectors": [...],
      "max_magnitude": 2.5
    },
    "flood_zones": {
      "type": "flood_zones",
      "zones": {...}
    }
  },
  "metadata": {
    "time": 100.0,
    "grid_resolution": {"nx": 100, "ny": 100}
  }
}
```

### WebSocket

#### GET /api/v1/websocket/stats
Get WebSocket connection statistics.

**Response:**
```json
{
  "total_connections": 5,
  "subscriptions": {
    "all": 5,
    "simulation": 3,
    "visualization": 2,
    "alerts": 5
  }
}
```

## WebSocket API

### Connection

Connect to WebSocket server at `ws://localhost:8765`

### Message Types

#### Client → Server

**Subscribe to Channel:**
```json
{
  "type": "subscribe",
  "channel": "simulation"
}
```

**Unsubscribe from Channel:**
```json
{
  "type": "unsubscribe",
  "channel": "simulation"
}
```

**Ping:**
```json
{
  "type": "ping"
}
```

**Get Status:**
```json
{
  "type": "get_status"
}
```

#### Server → Client

**Connection Established:**
```json
{
  "type": "connection_established",
  "message": "Connected to Flood Prediction World Model",
  "timestamp": "2024-01-15T10:30:00Z",
  "active_connections": 5
}
```

**Simulation Update:**
```json
{
  "type": "simulation_update",
  "timestamp": "2024-01-15T10:30:01Z",
  "data": {
    "time": 100.0,
    "water_depth": [[...]],
    "velocity_x": [[...]],
    "velocity_y": [[...]]
  }
}
```

**Alert:**
```json
{
  "type": "alert",
  "alert_type": "flood_warning",
  "message": "Elevated water levels detected",
  "severity": "medium",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "max_depth": 3.5,
    "location": [50, 50]
  }
}
```

**Prediction Update:**
```json
{
  "type": "prediction_update",
  "timestamp": "2024-01-15T10:30:00Z",
  "predictions": {
    "flood_risk": {
      "high": {"probability": 0.6},
      "severe": {"probability": 0.2}
    }
  }
}
```

**Pong (Response to Ping):**
```json
{
  "type": "pong",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Channels

- `all` - Receive all broadcast messages
- `simulation` - Real-time simulation updates
- `visualization` - Visualization data updates
- `predictions` - ML prediction updates
- `alerts` - System alerts and warnings

## Error Handling

### HTTP Status Codes

- `200 OK` - Request successful
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
  "error": "Invalid parameter",
  "message": "Grid resolution must be positive integers",
  "status_code": 400
}
```

## Code Examples

### Python

```python
import requests
import json

# Run simulation
response = requests.post(
    'http://localhost:8000/api/v1/simulation/run',
    json={
        'steps': 100,
        'output_format': 'full'
    }
)

result = response.json()
print(f"Simulation completed: {result['simulation']['total_steps']} steps")

# Get predictions
response = requests.post(
    'http://localhost:8000/api/v1/predictions/make',
    json={
        'prediction_type': 'flood_risk',
        'horizon': 24,
        'input_data': {
            'elevation': 5.0,
            'water_depth': 2.5
        }
    }
)

predictions = response.json()
print(f"High risk probability: {predictions['flood_risk']['high']['probability']}")
```

### JavaScript

```javascript
// Run simulation
fetch('http://localhost:8000/api/v1/simulation/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    steps: 100,
    output_format: 'full'
  })
})
.then(response => response.json())
.then(data => {
  console.log(`Simulation completed: ${data.simulation.total_steps} steps`);
});

// WebSocket connection
const ws = new WebSocket('ws://localhost:8765');

ws.onopen = () => {
  console.log('Connected to WebSocket');
  
  // Subscribe to simulation updates
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'simulation'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};
```

### cURL

```bash
# Health check
curl http://localhost:8000/health

# Run simulation
curl -X POST http://localhost:8000/api/v1/simulation/run \
  -H "Content-Type: application/json" \
  -d '{"steps": 100, "output_format": "full"}'

# Get terrain data
curl http://localhost:8000/api/v1/terrain/data

# Make predictions
curl -X POST http://localhost:8000/api/v1/predictions/make \
  -H "Content-Type: application/json" \
  -d '{
    "prediction_type": "flood_risk",
    "horizon": 24,
    "input_data": {
      "elevation": 5.0,
      "water_depth": 2.5
    }
  }'
```

## Rate Limiting

- Default rate limit: 100 requests per minute
- WebSocket messages: No limit, but excessive messages may be throttled

## Authentication

Currently, the API does not require authentication. For production deployments, implement:
- API key authentication
- OAuth 2.0
- JWT tokens

## Versioning

API version is included in the URL path: `/api/v1/...`

Future versions will use `/api/v2/...`, etc.

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/flood-prediction-world/issues
- Documentation: https://docs.flood-prediction-world.io
- Email: support@flood-prediction-world.io