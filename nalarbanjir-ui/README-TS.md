# Frontend TypeScript Port

This directory contains the TypeScript port of the existing JavaScript frontend code.

## Files

### Types (`types/`)
- `index.d.ts` - Global type definitions for Three.js and API responses

### Services (`services/`)
- `water_shaders.ts` - Shader definitions and presets
- `WaterShaderManager.ts` - Water surface rendering manager
- `TileStreamingController.ts` - Large terrain tile streaming
- `ProxyTileManager.ts` - Low-resolution proxy terrain
- `GISVisualizationController.ts` - GIS data loading and visualization
- `RiverGeometryManager.ts` - River geometry management
- `Scene3D.ts` - Main Three.js scene manager
- `index.ts` - Module exports

## Usage

### Import Services
```typescript
import * as THREE from 'three';
import { Scene3D, WaterShaderManager, TileStreamingController } from './services';

// Create scene
const scene3D = new Scene3D('threejs-canvas');

// Create water shader manager
const waterManager = new WaterShaderManager(scene3D.scene, scene3D.camera);

// Create tile streaming controller
const tileController = new TileStreamingController(scene3D.scene);
```

### Build
```bash
npm install
npm run build
```

## Migration Notes

### From JavaScript to TypeScript

1. **Type Annotations**: All class properties now have proper types
2. **Interfaces**: Added TypeScript interfaces for better type safety
3. **JSDoc Removed**: Comments moved to interface definitions
4. **Module Exports**: Replaced CommonJS exports with ES6 modules

### Key Changes

| JavaScript | TypeScript |
|------------|------------|
| `class MyClass { ... }` | `export class MyClass { ... }` |
| `const x: any = ...` | `const x: number = ...` |
| `export default` | `export { name }` |
| `module.exports` | ES6 imports/exports |

### Benefits

- **Type Safety**: Compile-time error detection
- **Better IDE Support**: Autocomplete and IntelliSense
- **Refactoring**: Safer code changes
- **Documentation**: TypeScript generates API documentation
- **Consistency**: Unified with existing Angular TypeScript codebase

## Integration with Angular

These services can be used in Angular components:

```typescript
import { inject, Injectable } from '@angular/core';
import { Scene3D, WaterShaderManager } from './frontend/services';

@Injectable({ providedIn: 'root' })
export class MyService {
  private scene3D = inject(Scene3D);
  private waterManager = new WaterShaderManager(this.scene3D.scene, this.scene3D.camera);
}
```