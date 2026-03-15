# Educational Tutorials - Flood Prediction World Model

## Table of Contents

1. [Introduction to Flood Prediction](#introduction)
2. [Tutorial 1: Basic Simulation](#tutorial-1-basic-simulation)
3. [Tutorial 2: Understanding Terrain Models](#tutorial-2-terrain-models)
4. [Tutorial 3: Machine Learning Predictions](#tutorial-3-ml-predictions)
5. [Tutorial 4: Visualization Techniques](#tutorial-4-visualization)
6. [Tutorial 5: Real-time Monitoring](#tutorial-5-real-time)
7. [Hands-on Exercises](#exercises)
8. [Assessment Questions](#assessment)

---

## Introduction

### What is Flood Prediction?

Flood prediction involves using mathematical models to simulate how water flows over terrain during flood events. By understanding these dynamics, we can:
- **Predict** flood risk before it happens
- **Assess** potential damage
- **Plan** evacuation routes
- **Design** better flood defenses

### The Physics Behind Floods

Floods are governed by the **Shallow Water Equations**:

```
∂h/∂t + ∂(hu)/∂x + ∂(hv)/∂y = 0          (Continuity)
∂(hu)/∂t + ... = -gh∂η/∂x + friction      (Momentum x)
∂(hv)/∂t + ... = -gh∂η/∂y + friction      (Momentum y)
```

Where:
- **h** = Water depth
- **u, v** = Velocity components
- **g** = Gravity (9.81 m/s²)
- **η** = Water surface elevation

---

## Tutorial 1: Basic Simulation

### Learning Objectives
- Run your first flood simulation
- Understand simulation parameters
- Interpret basic results

### Step-by-Step Guide

#### Step 1: Initialize the Environment

```python
import sys
sys.path.append('src')

from physics.shallow_water import ShallowWaterSolver
from physics.terrain import TerrainModel
import numpy as np
```

#### Step 2: Create Terrain

```python
# Create a simple terrain with a depression in the center
terrain_config = {
    'flood_thresholds': {
        'minor': 0.5,    # 0.5m - minor flooding
        'moderate': 1.0, # 1.0m - moderate flooding
        'major': 2.0,    # 2.0m - major flooding
        'severe': 3.0    # 3.0m - severe flooding
    }
}

terrain = TerrainModel(config=terrain_config, resolution=(50, 50))
print(f"Terrain created: {terrain.nx}x{terrain.ny} grid")
```

**Concept Check:** Why do we need different flood thresholds?

<details>
<summary>Answer</summary>
Different areas have different vulnerabilities. Urban areas flood at lower depths than rural areas. Buildings and infrastructure can be damaged at different water levels.
</details>

#### Step 3: Set Up Physics Solver

```python
physics_config = {
    'gravity': 9.81,           # m/s² - Earth's gravity
    'coriolis': 0.0,           # Effect of Earth's rotation (0 for small scales)
    'bottom_friction': 0.02,   # Friction coefficient (higher = rougher terrain)
    'time_step': 0.5,          # seconds between calculations
    'domain_x': 1000.0,        # meters - width of simulation area
    'domain_y': 1000.0         # meters - height of simulation area
}

solver = ShallowWaterSolver(
    config=physics_config, 
    grid_resolution=(50, 50)
)
```

**Key Parameters Explained:**
- **Gravity (9.81 m/s²)**: Controls how fast water flows downhill
- **Bottom Friction**: Represents roughness (vegetation, buildings, etc.)
- **Time Step**: Smaller = more accurate but slower
- **Domain Size**: Physical area being simulated

#### Step 4: Add Initial Water

```python
# Add water to the center of the grid
center_x, center_y = 25, 25
for i in range(20, 30):
    for j in range(20, 30):
        solver.state.depth[i, j] = 2.0  # 2 meters of water

print(f"Initial water volume: {np.sum(solver.state.depth):.2f} m³")
```

#### Step 5: Run Simulation

```python
# Run for 100 time steps
states = solver.evolve(steps=100)

print(f"Simulation completed!")
print(f"Final time: {states[-1].time:.2f} seconds")
print(f"Final water volume: {np.sum(states[-1].depth):.2f} m³")
```

#### Step 6: Analyze Results

```python
from physics.shallow_water import WavePropagationAnalyzer

analyzer = WavePropagationAnalyzer(solver)
wave_data = analyzer.analyze_wave_propagation(states[-1])

print(f"\nWave Analysis:")
print(f"  Mean wave speed: {wave_data['mean_celerity']:.2f} m/s")
print(f"  Kinetic energy: {np.mean(wave_data['kinetic_energy']):.2f} J")
print(f"  Potential energy: {np.mean(wave_data['potential_energy']):.2f} J")
```

### Exercise 1.1: Experiment with Parameters

Try changing these parameters and observe the effects:

1. **Double the gravity** (to simulate a different planet)
   - What happens to wave speed?
   
2. **Increase friction to 0.1**
   - How does the water spread differently?
   
3. **Use a smaller time step (0.1)**
   - Is the simulation more accurate? Does it take longer?

---

## Tutorial 2: Terrain Models

### Learning Objectives
- Understand terrain properties
- Learn about land use types
- Calculate flood zones

### Terrain Components

#### 1. Elevation

```python
# Access elevation data
elevation = terrain.elevation
print(f"Elevation range: {np.min(elevation):.2f}m to {np.max(elevation):.2f}m")
print(f"Mean elevation: {np.mean(elevation):.2f}m")
```

**Exercise 2.1:** Where would water accumulate first - high or low elevations?

<details>
<summary>Answer</summary>
Water flows downhill due to gravity, so it accumulates in low-lying areas (depressions, valleys). These are the first areas to flood.
</details>

#### 2. Land Use Types

```python
# Land use affects how water interacts with the surface
land_use_map = {
    0: 'water',        # Water bodies (rivers, lakes)
    1: 'urban',        # Cities and buildings
    2: 'agricultural', # Farmland
    3: 'forest',       # Trees and vegetation
    4: 'wetland',      # Marshes and swamps
    5: 'open_land'     # Fields and grassland
}

print("Land use distribution:")
unique, counts = np.unique(terrain.land_use, return_counts=True)
for land_type, count in zip(unique, counts):
    percentage = (count / terrain.land_use.size) * 100
    print(f"  {land_use_map[land_type]}: {percentage:.1f}%")
```

#### 3. Permeability

Permeability determines how much water soaks into the ground vs. runs off:

```python
# Check permeability by land use type
for i, name in land_use_map.items():
    mask = terrain.land_use == i
    if np.any(mask):
        avg_perm = np.mean(terrain.permeability[mask])
        print(f"{name}: {avg_perm:.2f} permeability")
```

**Permeability Scale:**
- 0.0 - Impermeable (concrete, buildings)
- 0.5 - Moderate (soil, grass)
- 1.0 - Highly permeable (sand, gravel)

### Identifying Flood Zones

```python
# Create a scenario with water
water_depth = np.zeros((50, 50))
water_depth[20:30, 20:30] = 2.5  # 2.5m in center

# Get flood zones
flood_zones = terrain.get_flood_zones(water_depth)

print("\nFlood Zone Analysis:")
for zone_type, cells in flood_zones.items():
    print(f"  {zone_type}: {len(cells)} cells")
```

### Exercise 2.2: Terrain Impact Analysis

**Scenario:** You need to plan a new housing development.

1. **Low-lying areas** (< 25th percentile elevation)
   - Risk: High flooding potential
   - Recommendation: Build flood defenses or avoid

2. **Urban areas** with low permeability
   - Risk: Fast runoff, overwhelmed drainage
   - Recommendation: Install retention ponds

3. **Wetlands**
   - Risk: Already saturated soil
   - Benefit: Natural flood buffer
   - Recommendation: Preserve as green space

Write code to identify the safest areas for development:

```python
# Find safe areas (high elevation + permeable)
safe_mask = (
    (terrain.elevation > np.percentile(terrain.elevation, 75)) &
    (terrain.permeability > 0.6) &
    (terrain.land_use != 1)  # Not urban
)

safe_percentage = np.sum(safe_mask) / safe_mask.size * 100
print(f"Safe development area: {safe_percentage:.1f}% of terrain")
```

---

## Tutorial 3: Machine Learning Predictions

### Learning Objectives
- Understand ML predictions
- Interpret flood risk probabilities
- Use predictions for decision-making

### How ML Predictions Work

The ML model analyzes multiple factors:
- **Terrain elevation** - How high is the land?
- **Water depth** - How much water is present?
- **Flow velocity** - How fast is water moving?
- **Land use** - What type of surface?
- **Historical patterns** - What happened before?

### Making Predictions

```python
from ml.model import MLModel, ModelConfig

# Initialize ML model
config = ModelConfig()
ml_model = MLModel(config)

# Make a prediction
prediction = ml_model.predict(
    prediction_type='flood_risk',
    horizon=24  # Predict 24 hours ahead
)

# Interpret results
print("Flood Risk Prediction (24-hour horizon):")
for risk_level in ['low', 'moderate', 'high', 'severe']:
    if risk_level in prediction:
        prob = prediction[risk_level]['probability']
        print(f"  {risk_level.capitalize()}: {prob*100:.1f}%")
```

### Understanding Risk Levels

**Low Risk (< 25%):**
- Normal conditions
- No action needed
- Continue monitoring

**Moderate Risk (25-50%):**
- Elevated water levels possible
- Prepare flood defenses
- Alert emergency services

**High Risk (50-75%):**
- Significant flooding likely
- Evacuate vulnerable areas
- Deploy emergency resources

**Severe Risk (> 75%):**
- Major flooding expected
- Immediate evacuation
- State of emergency

### Exercise 3.1: Prediction Confidence

```python
# Get prediction confidence
confidence = ml_model.get_prediction_confidence()

print("Prediction Confidence:")
print(f"  Overall: {confidence.get('overall', 'N/A')}")
print(f"  Flood Risk: {confidence.get('flood_risk', 'N/A')}")
print(f"  Flow Dynamics: {confidence.get('flow_dynamics', 'N/A')}")
```

**Discussion:** When should you trust a prediction?

<details>
<summary>Answer</summary>
High confidence (> 80%) predictions are reliable. Low confidence predictions need more data or human verification. Always combine ML predictions with domain expertise.
</details>

### Real-World Application

**Scenario:** A weather forecast predicts 100mm of rain in the next 24 hours.

```python
# Simulate heavy rainfall scenario
input_data = {
    'elevation': 10.0,
    'permeability': 0.3,
    'land_use_type': 1,  # Urban
    'water_depth': 0.5,  # Already some flooding
    'velocity_x': 0.5,
    'velocity_y': 0.2,
    'flow_rate': 15.0,   # High inflow from rain
    'flood_index': 0.6,
    'precipitation': 100.0,  # 100mm rain
    'seasonal_factor': 1.2
}

prediction = ml_model.predict(
    prediction_type='flood_risk',
    horizon=24
)

# Decision support
high_risk_prob = prediction.get('high', {}).get('probability', 0)
if high_risk_prob > 0.7:
    print("⚠️  ACTION REQUIRED: High flood risk!")
    print("   - Issue evacuation orders")
    print("   - Deploy sandbags")
    print("   - Alert emergency services")
elif high_risk_prob > 0.4:
    print("⚡ WARNING: Moderate flood risk")
    print("   - Monitor closely")
    print("   - Prepare flood defenses")
else:
    print("✓ Low risk - Continue monitoring")
```

---

## Tutorial 4: Visualization Techniques

### Learning Objectives
- Create visual representations of floods
- Interpret water surface maps
- Analyze flow vectors

### Water Surface Visualization

```python
from visualization.water_surface import WaterSurfaceRenderer

# Create renderer
vis_config = {
    'color_schemes': {
        'natural': {
            'water': '#3b82f6'  # Blue
        }
    }
}
renderer = WaterSurfaceRenderer(vis_config)

# Render water surface
water_surface = solver.get_water_surface()
elevation = solver.state.elevation

render_data = renderer.render(water_surface, elevation)

print(f"Water Surface:")
print(f"  Min depth: {render_data['min_depth']:.2f}m")
print(f"  Max depth: {render_data['max_depth']:.2f}m")
print(f"  Mean depth: {render_data['mean_depth']:.2f}m")
```

### Understanding the Visualization

**Color Coding:**
- Deep blue = Deep water (dangerous)
- Light blue = Shallow water (less dangerous)
- No color = No water (safe)

### Flow Vector Analysis

```python
from visualization.flow_vectors import FlowVectorRenderer, FlowAnalyzer

# Create renderer
flow_renderer = FlowVectorRenderer(vis_config)

# Get velocity data
velocity_x, velocity_y = solver.get_velocity_field()

# Render flow vectors
flow_render = flow_renderer.render(
    velocity_x, 
    velocity_y, 
    water_surface
)

print(f"\nFlow Analysis:")
print(f"  Max velocity: {flow_render['max_magnitude']:.2f} m/s")
print(f"  Mean velocity: {flow_render['mean_magnitude']:.2f} m/s")
print(f"  Vector count: {flow_render['vector_count']}")
```

### Interpreting Flow Vectors

**Arrow Direction:** Shows which way water is flowing
**Arrow Length:** Shows flow speed (longer = faster)

**Critical Thresholds:**
- < 0.5 m/s: Safe to walk through
- 0.5-1.0 m/s: Dangerous to walk
- 1.0-2.0 m/s: Can sweep away vehicles
- > 2.0 m/s: Can destroy buildings

### Exercise 4.1: Danger Zone Identification

```python
# Find areas with dangerous flow speeds
velocity_x, velocity_y = solver.get_velocity_field()
magnitude = np.sqrt(velocity_x**2 + velocity_y**2)

dangerous_mask = magnitude > 1.0  # Over 1 m/s
dangerous_cells = np.sum(dangerous_mask)

print(f"Dangerous areas: {dangerous_cells} cells")
print(f"Percentage of domain: {dangerous_cells/magnitude.size*100:.1f}%")
```

### Complete Visualization

```python
from visualization.renderer import VisualizationRenderer

# Create complete visualization
renderer = VisualizationRenderer(vis_config)
output = renderer.render(
    physics_solver=solver,
    terrain=terrain,
    output_format='full'
)

# Access different components
water_viz = output['visualization']['water_surface']
flow_viz = output['visualization']['flow_vectors']
flood_zones = output['visualization']['flood_zones']
```

---

## Tutorial 5: Real-time Monitoring

### Learning Objectives
- Set up WebSocket connections
- Receive real-time updates
- Handle alerts

### WebSocket Basics

WebSockets provide real-time communication between server and clients:

```javascript
// Connect to WebSocket server
const ws = new WebSocket('ws://localhost:8765');

// Connection opened
ws.onopen = function(event) {
    console.log('Connected to flood monitoring system');
    
    // Subscribe to simulation updates
    ws.send(JSON.stringify({
        type: 'subscribe',
        channel: 'simulation'
    }));
};

// Receive messages
ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    if (message.type === 'simulation_update') {
        updateVisualization(message.data);
    } else if (message.type === 'alert') {
        showAlert(message);
    }
};
```

### Handling Alerts

```javascript
function showAlert(alertMessage) {
    const severity = alertMessage.severity;
    const message = alertMessage.message;
    
    if (severity === 'critical') {
        // Red alert - immediate action
        document.body.style.backgroundColor = '#ffcccc';
        alert('🚨 CRITICAL: ' + message);
    } else if (severity === 'warning') {
        // Yellow alert - be prepared
        console.warn('⚠️ Warning: ' + message);
    } else {
        // Info - general notification
        console.log('ℹ️ Info: ' + message);
    }
}
```

### Exercise 5.1: Build a Simple Dashboard

Create a real-time dashboard that:
1. Shows current water depth
2. Displays flood risk level
3. Alerts when thresholds exceeded

```html
<!DOCTYPE html>
<html>
<head>
    <title>Flood Monitor</title>
    <style>
        .safe { background-color: #90EE90; }
        .warning { background-color: #FFD700; }
        .danger { background-color: #FF6B6B; }
    </style>
</head>
<body>
    <h1>Real-time Flood Monitor</h1>
    <div id="status" class="safe">
        <h2>Status: <span id="risk-level">Low Risk</span></h2>
        <p>Water Depth: <span id="water-depth">0.0</span>m</p>
    </div>
    
    <script>
        const ws = new WebSocket('ws://localhost:8765');
        
        ws.onmessage = function(event) {
            const msg = JSON.parse(event.data);
            
            if (msg.type === 'simulation_update') {
                const depth = msg.data.water_depth;
                document.getElementById('water-depth').textContent = 
                    depth.toFixed(2);
                
                // Update status color
                const status = document.getElementById('status');
                if (depth > 2.0) {
                    status.className = 'danger';
                    document.getElementById('risk-level').textContent = 
                        'HIGH RISK';
                } else if (depth > 1.0) {
                    status.className = 'warning';
                    document.getElementById('risk-level').textContent = 
                        'Moderate Risk';
                }
            }
        };
    </script>
</body>
</html>
```

---

## Hands-on Exercises

### Exercise 1: Dam Break Simulation

**Scenario:** A dam holding back 5 meters of water suddenly fails.

**Task:** 
1. Set up initial conditions with high water on one side
2. Run simulation
3. Measure how fast the flood wave travels
4. Identify which areas flood first

```python
# Setup: High water on left side, dry on right
for i in range(50):
    for j in range(25):  # Left half
        solver.state.depth[i, j] = 5.0
    for j in range(25, 50):  # Right half
        solver.state.depth[i, j] = 0.0

# Run and measure wave propagation
states = solver.evolve(steps=50)
```

### Exercise 2: Urban Flood Planning

**Scenario:** Plan flood defenses for a city.

**Tasks:**
1. Identify critical infrastructure (hospitals, schools)
2. Calculate flood risk for each building
3. Design retention ponds to reduce peak flow
4. Test different scenarios

### Exercise 3: Climate Change Impact

**Scenario:** Predict flooding under climate change (more intense rainfall).

**Tasks:**
1. Baseline: Run simulation with normal rainfall
2. Scenario: Increase precipitation by 50%
3. Compare flood extent and depth
4. Calculate economic impact

---

## Assessment Questions

### Multiple Choice

1. What equation governs flood water flow?
   - a) Newton's laws
   - b) Shallow water equations ✓
   - c) Einstein's relativity
   - d) Ohm's law

2. Which terrain type has the lowest permeability?
   - a) Forest
   - b) Urban/concrete ✓
   - c) Wetland
   - d) Agricultural

3. A flow velocity of 2.5 m/s is:
   - a) Safe for walking
   - b) Can sweep away cars ✓
   - c) Barely noticeable
   - d) Impossible in floods

### Short Answer

4. Why is the time step size important in simulations?

<details>
<summary>Answer</summary>
Smaller time steps give more accurate results but require more computation. Too large time steps can make the simulation unstable or inaccurate.
</details>

5. How does machine learning improve flood prediction?

<details>
<summary>Answer</summary>
ML can identify patterns in historical data, predict future states based on multiple factors simultaneously, and provide confidence estimates for predictions.
</details>

### Practical Problem

6. **Design Challenge:** 
   
   A town has:
   - 1000 residents
   - 1 hospital at low elevation
   - 1 school at moderate elevation
   - Mixed terrain (30% urban, 40% agricultural, 30% forest)
   
   Create a flood response plan that includes:
   - Early warning thresholds
   - Evacuation routes
   - Critical infrastructure protection
   - Resource allocation

---

## Additional Resources

### For Students
- **Interactive Simulations:** Try different scenarios in the Jupyter notebook
- **Video Tutorials:** Watch physics explanations on Khan Academy
- **Data Analysis:** Use Python pandas to analyze simulation outputs

### For Teachers
- **Lesson Plans:** 5-day curriculum with labs and assessments
- **Discussion Questions:** Promote critical thinking about flood management
- **Group Projects:** Design flood-resilient communities

### For Researchers
- **API Documentation:** Integrate with external datasets
- **Model Validation:** Compare predictions with historical flood events
- **Extension Guide:** Add new physics models or ML architectures

---

## Conclusion

You now understand:
- ✓ How flood simulations work
- ✓ The role of terrain and land use
- ✓ How ML improves predictions
- ✓ How to visualize and interpret results
- ✓ Real-time monitoring techniques

**Next Steps:**
1. Run your own experiments
2. Explore the API documentation
3. Build custom visualizations
4. Contribute to the project!

---

## Glossary

- **Celerity**: Wave speed in water
- **Permeability**: How easily water flows through a material
- **Hydraulic**: Related to water flow and pressure
- **Coriolis effect**: Earth's rotation effect on moving fluids
- **ML (Machine Learning)**: Computer algorithms that learn from data
- **Time step**: Discrete interval in simulation time
- **Grid resolution**: Spatial detail of simulation (cells per area)