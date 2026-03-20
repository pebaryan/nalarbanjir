# TypeScript Services Directory

This directory contains TypeScript services and type definitions for the nalarbanjir frontend application.

## Directory Structure

```
services/
├── WaterShaderManager.ts      # Water surface rendering
├── TileStreamingController.ts # Large terrain tile streaming
├── ProxyTileManager.ts        # Proxy terrain preview
├── GISVisualizationController.ts # GIS data loading
├── RiverGeometryManager.ts    # River geometry management
├── Scene3D.ts                 # Main Three.js scene manager
├── index.ts                   # Module exports
└── README.md                  # This file
```

## Type Definitions

The type definitions are in the `types/` directory:
- `types/index.d.ts` - Global type definitions
- `types/water_shaders.ts` - Shader definitions and presets

## Services

### WaterShaderManager
Manages water surface rendering with custom shaders for realistic water effects including:
- Wave animation
- Depth-based coloring
- Lighting effects
- Preset configurations

### TileStreamingController
Implements LOD (Level of Detail) based terrain rendering:
- Automatic tile loading/unloading
- Camera-based visibility tracking
- Tile caching for performance
- Progressive refinement

### ProxyTileManager
Provides immediate visualization for large terrain datasets:
- Low-resolution preview rendering
- Background tile loading
- Progressive refinement as detailed tiles become available

### GISVisualizationController
Manages GIS data loading and visualization:
- Terrain and water data loading
- Simulation management
- View state tracking

### RiverGeometryManager
Handles river geometry operations:
- River data CRUD operations
- GeoJSON export
- Mesh generation for solvers

### Scene3D
Main Three.js scene manager:
- Scene initialization
- Camera and renderer setup
- Event handling
- Terrain and water management

## Usage in Angular

```typescript
import { Scene3D, WaterShaderManager } from './services';
import { inject, Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class VisualizationService {
  private scene3D = inject(Scene3D);
  private waterManager = new WaterShaderManager(
    this.scene3D.scene,
    this.scene3D.camera
  );

  loadTerrain(file: File): Promise<void> {
    return this.waterManager.loadTerrainFromFile(file);
  }
}
```

## Build

To build the TypeScript services:

```bash
cd nalarbanjir-ui
npm install
npm run build
```

## TypeScript Configuration

The tsconfig.json file in the root directory configures the TypeScript compiler for both the Angular application and the frontend services.