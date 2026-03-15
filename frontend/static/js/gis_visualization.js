/**
 * GIS 3D Visualization Controller
 * 
 * Manages the connection between GIS backend data and Three.js frontend
 * Provides high-level API for loading and visualizing terrain and water data.
 */

class GISVisualizationController {
    constructor(scene3d) {
        this.scene = scene3d;
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
     * Load terrain from DTM file
     * @param {File} file - GeoTIFF or other DTM file
     * @returns {Promise} - Resolves when terrain is loaded
     */
    async loadTerrainFromFile(file) {
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
                this.onError('terrain', error);
            }
            throw error;
        } finally {
            this.isLoading = false;
        }
    }
    
    /**
     * Load terrain mesh from server URL
     * @param {string} meshUrl - URL to mesh JSON file
     */
    async loadTerrainFromServer(meshUrl) {
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
     * @param {Object} waterData - Water depth and surface data from server
     */
    loadWaterSurface(waterData) {
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
     * @param {Float32Array} waterDepthArray - New water depth values
     */
    updateWaterSurface(waterDepthArray) {
        this.scene.updateWaterHeight(waterDepthArray);
    }
    
    /**
     * Run flood simulation
     * @param {Object} params - Simulation parameters
     * @returns {Promise} - Simulation results
     */
    async runSimulation(params) {
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
                this.onError('simulation', error);
            }
            throw error;
        }
    }
    
    /**
     * Animate through simulation timesteps
     * @param {Object} results - Simulation results with timestep data
     */
    async animateSimulation(results) {
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
    exportScreenshot() {
        return this.scene.takeScreenshot();
    }
    
    /**
     * Get current view state
     * @returns {Object} - Camera position and settings
     */
    getViewState() {
        return {
            camera: {
                position: this.scene.getCameraPosition(),
                target: this.scene.controls.target
            },
            hasTerrain: this.currentDtm !== null,
            hasWater: this.currentWaterMesh !== null
        };
    }
    
    /**
     * Reset view to default
     */
    resetView() {
        this.scene.setCameraView('perspective');
    }
    
    /**
     * Set view mode
     * @param {string} mode - 'top', 'front', 'side', 'perspective'
     */
    setViewMode(mode) {
        this.scene.setCameraView(mode);
    }
    
    /**
     * Toggle water visibility
     * @param {boolean} visible
     */
    toggleWater(visible) {
        if (this.scene.water) {
            this.scene.water.visible = visible;
        }
    }
    
    /**
     * Toggle terrain wireframe
     * @param {boolean} wireframe
     */
    toggleTerrainWireframe(wireframe) {
        if (this.scene.terrain) {
            this.scene.terrain.material.wireframe = wireframe;
        }
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GISVisualizationController };
}