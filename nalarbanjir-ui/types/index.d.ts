/**
 * Global TypeScript definitions for the flood prediction application
 */

// Three.js type definitions
declare module 'three' {
    export class Scene { }
    export class Camera { }
    export class Renderer { }
    export class Mesh { }
    export class BufferGeometry { }
    export class Material { }
    export class ShaderMaterial { }
    export class MeshStandardMaterial { }
    export class OrbitControls { }
    export class Raycaster { }
    export class GridHelper { }
    export class AxesHelper { }
    export class Texture { }
    export class PointLight { }
    export class DirectionalLight { }
    export class AmbientLight { }
    export class SpotLight { }
    export class SpotLightHelper { }
    export class Box3 { }
    export class BoxHelper { }
    export class PlaneGeometry { }
    export class BufferAttribute { }
    export class Vector3 { }
    export class Vector2 { }
    export class Color { }
    export class Vector4 { }
    export class Matrix4 { }
    export class NormalMatrix { }
    export type Object3D = Mesh | any;
    export interface WebGLRendererOptions {
        canvas?: HTMLCanvasElement;
        antialias?: boolean;
        alpha?: boolean;
    }
}

// API Response types
interface ApiResponse<T> {
    ok: boolean;
    message?: string;
    detail?: string;
}

interface MeshData {
    vertices: number[];
    indices: number[];
    normals: number[];
    uvs: number[];
}

interface TerrainMetadata {
    crs: string;
    bounds: {
        minX: number;
        minY: number;
        maxX: number;
        maxY: number;
    };
}

// Water mesh interface
interface WaterMesh {
    vertices: Float32Array;
    normals: Float32Array;
    uvs: Float32Array;
    indices: Uint32Array;
}

// River geometry types
interface RiverGeometry {
    type: string;
    coordinates: number[][];
}

interface HydraulicParams {
    width: number;
    depth: number;
    slope: number;
    manning_n: number;
    discharge: number;
    velocity: number;
}

// Tile data types
interface TileData {
    vertices: number[];
    indices: number[];
    normals?: number[];
    lod_level?: number;
}

// Simulation types
interface SimulationProgress {
    type: 'simulation';
    current: number;
    total: number;
    percent: number;
}

// DOM Element types
interface DOMElement {
    value: string;
    checked?: boolean;
    selected?: boolean;
}

// File upload types
interface UploadProgress {
    type: 'upload';
    file: string;
    percent: number;
}

// WebSocket message types
interface WebSocketMessage {
    type: string;
    data?: any;
    elapsed_time?: number;
    step?: number;
    message?: string;
}

// Tile progress types
interface TileProgress {
    status: 'processing' | 'completed' | 'error';
    completed_tiles: number;
    total_tiles: number;
    message?: string;
}

// Three.js geometry interface
interface ThreejsGeometry {
    data: {
        attributes: {
            position?: {
                array: number[];
            };
            index?: {
                array: number[];
            };
            normal?: {
                array: number[];
            };
            uv?: {
                array: number[];
            };
        };
    };
}