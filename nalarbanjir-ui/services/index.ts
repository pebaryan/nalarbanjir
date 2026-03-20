/**
 * Frontend Services Module
 *
 * Exports all frontend services and types for TypeScript usage
 */

// Re-export types
export * from '../types/index';
export * from './water_shaders';

// Re-export services
export { WaterShaderManager } from './WaterShaderManager';
export { TileStreamingController } from './TileStreamingController';
export { ProxyTileManager } from './ProxyTileManager';
export { GISVisualizationController } from './GISVisualizationController';
export { RiverGeometryManager } from './RiverGeometryManager';
export { Scene3D } from './Scene3D';