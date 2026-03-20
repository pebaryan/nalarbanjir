/**
 * GIS 3D Visualization Controller
 *
 * Manages the connection between GIS backend data and Three.js frontend
 * Provides high-level API for loading and visualizing terrain and water data.
 */

import * as THREE from 'three';
import { type WaterMeshData } from '../types/index';

/**
 * Interface for GIS load callbacks
 */
export interface GISLoadCallbacks {
    onProgress?: (progress: SimulationProgress) => void;
    onLoadComplete?: (type: string, result: any) => void;
    onError?: (type: string, error: Error) => void;
}

/**
 * Simulation progress
 */
interface SimulationProgress {
    type: 'simulation';
    current: number;
    total: number;
    percent: number;
}

/**
 * GISVisualizationController - Class for managing GIS data loading
 */
export class GISVisualizationController {
    private scene: THREE.Scene;
    private apiBaseUrl: string;
    private currentDtm: any;
    private currentWaterMesh: any;
    private isLoading: boolean;

    // Event callbacks
    private onProgress: ((progress: SimulationProgress) => void) | null;
    private onLoadComplete: ((type: string, result: any) => void) | null;
    private onError: ((type: string, error: Error) => void) | null;

    /**
     * Create a new GIS visualization controller
     * @param scene - The Three.js scene
     */
    constructor(scene: THREE.Scene) {
        this.scene = scene;
        this.apiBaseUrl = '/api';
        this.currentDtm = null;
        this.currentWaterMesh = null;
        this.isLoading = false;

        // Event callbacks
        this.onProgress = null;
        this.onLoadComplete = null;
        this.onError = null;
    }

    /**
     * Set event callbacks
     * @param callbacks - Callback functions
     */
    setCallbacks(callbacks: GISLoadCallbacks): void {
        this.onProgress = callbacks.onProgress ?? null;
        this.onLoadComplete = callbacks.onLoadComplete ?? null;
        this.onError = callbacks.onError ?? null;
    }

    /**
     * Load terrain from DTM file
     * @param file - GeoTIFF or other DTM file
     * @returns {Promise} - Resolves when terrain is loaded
     */
    async loadTerrainFromFile(file: File): Promise<void> {
        console.log('Loading terrain from file:', file.name);
        this.isLoading = true;

        try {
            // Create form data
            const formData = new FormData();
            formData.append('file', file);
            formData.append('type', 'terrain');

            // Upload and process on server
            const response = await fetch(`${this.apiBaseUrl}/gis/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }

            const result = await response.json();

            // Load the generated mesh
            await this.loadTerrainFromServer(result.mesh_url);

            if (this.onLoadComplete) {
                this.onLoadComplete('terrain', result);
            }

        } catch (error) {
            console.error('Error loading terrain:', error);
            if (this.onError) {
                this.onError('terrain', error as Error);
            }
            throw error;
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Load terrain mesh from server URL
     * @param meshUrl - URL to mesh JSON file
     */
    async loadTerrainFromServer(meshUrl: string): Promise<void> {
        console.log('Loading terrain mesh:', meshUrl);

        const response = await fetch(meshUrl);
        if (!response.ok) {
            throw new Error(`Failed to load mesh: ${response.statusText}`);
        }

        const meshData = await response.json();
        this.scene.loadTerrain(meshData);
        this.currentDtm = meshData;

        console.log('Terrain loaded successfully');
    }

    /**
     * Load water surface data
     * @param waterData - Water depth and surface data from server
     */
    loadWaterSurface(waterData: { mesh?: WaterMeshData; color?: number; opacity?: number }): void {
        console.log('Loading water surface');

        if (waterData.mesh) {
            this.scene.loadWater(waterData.mesh, {
                color: waterData.color || 0x006994,
                opacity: waterData.opacity || 0.7
            });
            this.currentWaterMesh = waterData.mesh;
        }
    }

    /**
     * Update water surface in real-time
     * @param waterDepthArray - New water depth values
     */
    updateWaterSurface(waterDepthArray: Float32Array): void {
        this.scene.updateWaterHeight(waterDepthArray);
    }

    /**
     * Run flood simulation
     * @param params - Simulation parameters
     * @returns {Promise} - Simulation results
     */
    async runSimulation(params: any): Promise<any> {
        console.log('Running flood simulation', params);

        try {
            const response = await fetch(`${this.apiBaseUrl}/simulate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(params)
            });

            if (!response.ok) {
                throw new Error(`Simulation failed: ${response.statusText}`);
            }

            const results = await response.json();

            // Animate through simulation timesteps
            await this.animateSimulation(results);

            return results;

        } catch (error) {
            console.error('Simulation error:', error);
            if (this.onError) {
                this.onError('simulation', error as Error);
            }
            throw error;
        }
    }

    /**
     * Animate through simulation timesteps
     * @param results - Simulation results with timestep data
     */
    private async animateSimulation(results: any): Promise<void> {
        const timesteps = results.timesteps || [];

        for (let i = 0; i < timesteps.length; i++) {
            const step = timesteps[i];

            // Update progress
            if (this.onProgress) {
                this.onProgress({
                    type: 'simulation',
                    current: i + 1,
                    total: timesteps.length,
                    percent: ((i + 1) / timesteps.length) * 100
                });
            }

            // Update water surface
            if (step.water_mesh) {
                this.loadWaterSurface({
                    mesh: step.water_mesh,
                    opacity: 0.7
                });
            }

            // Wait for next frame (60fps = ~16ms)
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        if (this.onLoadComplete) {
            this.onLoadComplete('simulation', results);
        }
    }

    /**
     * Export current view as image
     * @returns {string} - Data URL of screenshot
     */
    exportScreenshot(): string {
        return this.scene.takeScreenshot();
    }

    /**
     * Get current view state
     * @returns Object with camera position and settings
     */
    getViewState(): {
        camera: {
            position: THREE.Vector3;
            target: THREE.Vector3;
        };
        hasTerrain: boolean;
        hasWater: boolean;
    } {
        return {
            camera: {
                position: this.scene.getCameraPosition(),
                target: this.scene.controls?.target ?? new THREE.Vector3()
            },
            hasTerrain: this.currentDtm !== null,
            hasWater: this.currentWaterMesh !== null
        };
    }

    /**
     * Reset view to default
     */
    resetView(): void {
        this.scene.setCameraView('perspective');
    }

    /**
     * Set view mode
     * @param mode - 'top', 'front', 'side', 'perspective'
     */
    setViewMode(mode: string): void {
        this.scene.setCameraView(mode);
    }

    /**
     * Toggle water visibility
     * @param visible - Whether water should be visible
     */
    toggleWater(visible: boolean): void {
        if (this.scene.water) {
            this.scene.water.visible = visible;
        }
    }

    /**
     * Toggle terrain wireframe
     * @param wireframe - Whether terrain should be wireframe
     */
    toggleTerrainWireframe(wireframe: boolean): void {
        if (this.scene.terrain) {
            this.scene.terrain.material.wireframe = wireframe;
        }
    }
}