# JavaScript to TypeScript Porting Guide

## Overview

This guide documents the porting of JavaScript files to TypeScript in the nalarbanjir codebase.

## Files Ported

### 1. Water Shaders (`frontend/types/water_shaders.ts`)
**Original:** `./frontend/static/js/water_shaders.js`

**Changes:**
- Converted JSDoc comments to TypeScript interfaces
- Added export statements
- Created `WaterPreset` interface
- Exported preset configuration

**Key Features:**
- Vertex shader for wave animation
- Fragment shader for water coloring
- Configuration presets (calm, moderate, rough, flood)

### 2. Water Shader Manager (`frontend/services/WaterShaderManager.ts`)
**Original:** `./frontend/static/js/water_shader_manager.js`

**Changes:**
- Added TypeScript interfaces for water mesh data
- Added configuration options interface
- Added water mesh entry interface
- Improved error handling
- Made class properties typed

**Key Methods:**
- `createWaterMesh()` - Create water mesh from geometry
- `removeWaterMesh()` - Remove water mesh from scene
- `update()` - Update shader uniforms in animation loop
- `setWaveParameters()` - Configure wave properties
- `setWaterColor()` - Set water colors
- `setLighting()` - Configure lighting
- `applyPreset()` - Apply configuration preset

### 3. Tile Streaming Controller (`frontend/services/TileStreamingController.ts`)
**Original:** `./frontend/static/js/tile_streaming.js`

**Changes:**
- Added TypeScript interface for tile data
- Added streaming configuration interface
- Improved camera tracking with type safety
- Made loading queue typed
- Added cache management with proper types

**Key Features:**
- LOD (Level of Detail) switching
- Tile caching for performance
- Automatic tile loading/unloading
- Progress tracking

### 4. Proxy Tile Manager (`frontend/services/ProxyTileManager.ts`)
**Original:** `./frontend/static/js/proxy_tiles.js`

**Changes:**
- Added TypeScript interface for tile data
- Added status tracking
- Improved error handling
- Made tile data typed

**Key Features:**
- Low-resolution preview rendering
- Background tile loading
- Progressive refinement
- Auto-cleanup of proxy mesh

### 5. GIS Visualization Controller (`frontend/services/GISVisualizationController.ts`)
**Original:** `./frontend/static/js/gis_visualization.js`

**Changes:**
- Added TypeScript interfaces for load callbacks
- Added simulation progress interface
- Improved error handling
- Made all callbacks properly typed

**Key Methods:**
- `loadTerrainFromFile()` - Load terrain from DTM file
- `loadTerrainFromServer()` - Load terrain mesh from URL
- `loadWaterSurface()` - Load water surface data
- `updateWaterSurface()` - Update water in real-time
- `runSimulation()` - Run flood simulation
- `exportScreenshot()` - Export view as image

### 6. River Geometry Manager (`frontend/services/RiverGeometryManager.ts`)
**Original:** `./frontend/static/js/river_entry.js`

**Changes:**
- Added TypeScript interfaces for river data
- Added TypeScript interface for river mesh data
- Improved error handling
- Made all API calls typed

**Key Methods:**
- `saveRiver()` - Save a new river
- `loadRivers()` - Load all rivers
- `exportRiver()` - Export river as GeoJSON
- `getRiverMesh()` - Get river mesh for solver
- `deleteRiver()` - Delete a river

### 7. Scene 3D (`frontend/services/Scene3D.ts`)
**Original:** `./frontend/static/js/threejs_scene.js`

**Changes:**
- Added TypeScript types for all properties
- Improved raycaster and mouse tracking
- Made scene components typed
- Added proper disposal methods

**Key Features:**
- Three.js scene initialization
- Camera and renderer setup
- Light configuration
- Terrain and water management
- View controls

### 8. Global Type Definitions (`frontend/types/index.d.ts`)
**New File**

**Purpose:**
- Define global TypeScript types for the application
- Extend Three.js types
- Define API response types
- Define DOM element types
- Define simulation and tile data types

## Type Definitions

### Key Interfaces

```typescript
// Three.js extensions
declare module 'three' { ... }

// API responses
interface ApiResponse<T> { ... }
interface MeshData { ... }

// Water mesh
interface WaterMeshData { ... }

// River data
interface RiverData { ... }
interface RiverMeshData { ... }

// Tile data
interface TileData { ... }

// WebSocket messages
interface WebSocketMessage { ... }

// Simulation progress
interface SimulationProgress { ... }
```

## Migration Process

### Step 1: Analyze JavaScript Code
1. Read the JavaScript file
2. Identify class structures and methods
3. Note all data types used
4. Identify event handlers and callbacks

### Step 2: Create Type Definitions
1. Create interfaces for all data structures
2. Define return types for methods
3. Add type annotations for parameters

### Step 3: Convert JavaScript to TypeScript
1. Add `export` to classes and interfaces
2. Replace `any` types with specific types
3. Add type annotations to parameters
4. Replace CommonJS exports with ES6 exports

### Step 4: Improve Documentation
1. Keep JSDoc comments for complex logic
2. Add inline comments for type safety
3. Create interface documentation

### Step 5: Add Error Handling
1. Use typed errors
2. Add proper try-catch blocks
3. Log errors with context

## Benefits of TypeScript Port

1. **Type Safety**
   - Catch errors at compile-time
   - Better IDE support
   - Self-documenting code

2. **Better Code Quality**
   - Consistent code style
   - Automatic validation
   - Improved maintainability

3. **Integration**
   - Works with existing Angular TypeScript codebase
   - Shared types and interfaces
   - Unified development workflow

4. **Performance**
   - No runtime type checking overhead
   - Optimized compilation
   - Better tree-shaking

## Usage Examples

### Using Services in Components

```typescript
import { Component, inject } from '@angular/core';
import { Scene3D, WaterShaderManager, TileStreamingController } from '../../frontend/services';

@Component({ ... })
export class MyComponent {
  private scene3D = inject(Scene3D);
  private waterManager = new WaterShaderManager(
    this.scene3D.scene,
    this.scene3D.camera
  );
  private tileController = new TileStreamingController(this.scene3D.scene);

  loadTerrain(file: File): Promise<void> {
    return this.waterManager.loadTerrainFromFile(file);
  }
}
```

### Using Type Definitions

```typescript
import { type SimulationProgress, type WaterMeshData } from '../../frontend/services';

function handleProgress(progress: SimulationProgress): void {
  console.log(`Progress: ${progress.percent}%`);
}

function renderWater(mesh: WaterMeshData): void {
  // Type-safe access to mesh properties
  const vertices = mesh.vertices;
}
```

## Next Steps

1. **Test All Services**
   - Verify all functionality works
   - Check for TypeScript compilation errors
   - Test in browser

2. **Create Angular Services**
   - Wrap TypeScript classes in Angular services
   - Use Angular dependency injection
   - Integrate with Angular components

3. **Add Unit Tests**
   - Test TypeScript classes
   - Verify type safety
   - Mock external dependencies

4. **Documentation**
   - Add API documentation
   - Create usage examples
   - Maintain migration guide

## Common Issues and Solutions

### Issue: Three.js Types Not Found
**Solution:** Ensure `three` package is installed:
```bash
npm install three@0.160.0
```

### Issue: Module Resolution Errors
**Solution:** Check `tsconfig.json` settings and ensure correct path mappings.

### Issue: Type Compatibility
**Solution:** Use type assertions or create adapter interfaces when needed.

## Conclusion

This porting process transforms JavaScript code into modern TypeScript, improving code quality, type safety, and maintainability while maintaining full functionality. The TypeScript services can be integrated with the existing Angular codebase for a unified development experience.