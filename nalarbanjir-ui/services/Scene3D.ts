/**
 * Three.js 3D Map Visualization Module
 *
 * Provides 3D terrain and water visualization using Three.js
 * with support for GIS data import and real-time updates.
 */

import * as THREE from 'three';
import { type WaterMeshData } from '../types/index';
import { WaterShaderManager } from './WaterShaderManager';

// ============================================================================
// Scene3D - Main 3D scene manager
// ============================================================================

export class Scene3D {
    private canvas: HTMLCanvasElement;
    private scene: THREE.Scene;
    private camera: THREE.PerspectiveCamera;
    private renderer: THREE.WebGLRenderer;
    private controls: THREE.OrbitControls;
    private terrain: THREE.Mesh | null;
    private water: THREE.Mesh | null;
    public waterShaderManager: WaterShaderManager | null;
    private lights: THREE.Light[];
    public initialized: boolean;

    // Configuration
    private config = {
        backgroundColor: 0x87CEEB,  // Sky blue
        fogDensity: 0.002,
        shadows: true,
        antialias: true
    };

    // Raycaster for mouse tracking
    private raycaster: THREE.Raycaster;
    private mouse: THREE.Vector2;
    private statusElement: HTMLElement | null;

    // Terrain info
    private terrainBounds?: {
        minX: number;
        minY: number;
        maxX: number;
        maxY: number;
        minElevation: number;
        maxElevation: number;
    };
    private terrainBoxHelper: THREE.BoxHelper | null;

    /**
     * Create a new 3D scene
     * @param canvasId - Canvas element ID
     */
    constructor(canvasId: string) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas element '${canvasId}' not found`);
        }

        this.scene = null!;
        this.camera = null!;
        this.renderer = null!;
        this.controls = null!;
        this.terrain = null;
        this.water = null;
        this.waterShaderManager = null;
        this.lights = [];
        this.initialized = false;

        this.init();
    }

    /**
     * Initialize the scene
     */
    init(): void {
        console.log('Initializing 3D Scene...');

        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(this.config.backgroundColor);
        // FOG DISABLED for better visibility
        // this.scene.fog = new THREE.FogExp2(this.config.backgroundColor, this.config.fogDensity);

        // Ensure canvas has size (it might be 0 if section is hidden)
        let canvasWidth = this.canvas.clientWidth;
        let canvasHeight = this.canvas.clientHeight;

        if (canvasWidth === 0 || canvasHeight === 0) {
            console.warn('Canvas has no size, setting default dimensions');
            // Set explicit size on canvas element
            this.canvas.style.width = '100%';
            this.canvas.style.height = '100%';
            this.canvas.width = 1336;  // Default width
            this.canvas.height = 600;  // Default height
            canvasWidth = 1336;
            canvasHeight = 600;
        }

        // Create camera
        const aspect = canvasWidth / canvasHeight;
        this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 10000);
        this.camera.position.set(500, 500, 500);
        this.camera.lookAt(0, 0, 0);

        // Create renderer
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: this.config.antialias,
            alpha: true
        });
        this.renderer.setSize(canvasWidth, canvasHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = this.config.shadows;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        console.log('Renderer created with size:', canvasWidth, 'x', canvasHeight);

        // Add lights
        this.setupLights();

        // Add a helper grid so we can see the scene is working
        // Position it below the terrain to avoid overlap
        const gridHelper = new THREE.GridHelper(1000, 20, 0x000000, 0x333333);
        gridHelper.position.y = -10; // Move below terrain
        this.scene.add(gridHelper);
        console.log('Added grid helper (dark colors, below terrain)');

        // Add axes helper
        const axesHelper = new THREE.AxesHelper(100);
        this.scene.add(axesHelper);
        console.log('Added axes helper');

        // Add controls
        this.setupControls();

        // Setup mouse tracking for terrain info
        this.setupMouseTracking();

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize(), false);

        // Initialize water shader manager (Phase 5)
        this.initWaterShaderManager();

        this.initialized = true;
        console.log('3D Scene initialized');

        // Start render loop
        this.animate();
    }

    /**
     * Initialize water shader manager
     */
    private initWaterShaderManager(): void {
        // Phase 5: Initialize water shader manager for realistic water rendering
        try {
            this.waterShaderManager = new WaterShaderManager(this.scene, this.camera, {
                preset: 'calm',
                enableReflection: false,
                enableRefraction: false,
                enableNormalMap: true
            });
            console.log('Water shader manager initialized');
        } catch (error) {
            console.warn('Failed to initialize water shader manager:', error);
            this.waterShaderManager = null;
        }
    }

    /**
     * Set up scene lights
     */
    private setupLights(): void {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        this.scene.add(ambientLight);
        this.lights.push(ambientLight);

        // Directional light (sun)
        const sunLight = new THREE.DirectionalLight(0xffffff, 0.8);
        sunLight.position.set(500, 1000, 500);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 2048;
        sunLight.shadow.mapSize.height = 2048;
        sunLight.shadow.camera.near = 0.5;
        sunLight.shadow.camera.far = 2000;
        sunLight.shadow.camera.left = -1000;
        sunLight.shadow.camera.right = 1000;
        sunLight.shadow.camera.top = 1000;
        sunLight.shadow.camera.bottom = -1000;
        this.scene.add(sunLight);
        this.lights.push(sunLight);

        // Hemisphere light (sky/ground)
        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.3);
        hemiLight.position.set(0, 500, 0);
        this.scene.add(hemiLight);
        this.lights.push(hemiLight);
    }

    /**
     * Set up orbit controls
     */
    private setupControls(): void {
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 10;
        this.controls.maxDistance = 5000;
        this.controls.maxPolarAngle = Math.PI / 2 - 0.1;  // Don't go below ground
    }

    /**
     * Set up mouse tracking for terrain info
     */
    private setupMouseTracking(): void {
        // Raycaster for mouse intersection
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        // Create status display element
        this.createStatusDisplay();

        // Mouse move handler
        this.canvas.addEventListener('mousemove', (event) => {
            this.onMouseMove(event);
        }, false);

        // Mouse leave handler
        this.canvas.addEventListener('mouseleave', () => {
            this.hideStatus();
        }, false);

        console.log('Mouse tracking setup complete');
    }

    /**
     * Create status display element
     */
    private createStatusDisplay(): void {
        // Create floating status element
        this.statusElement = document.createElement('div');
        this.statusElement.id = 'terrain-status';
        this.statusElement.style.cssText = `
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-family: monospace;
        `;
        this.canvas.parentElement?.appendChild(this.statusElement);
    }

    /**
     * Mouse move handler
     */
    private onMouseMove(event: MouseEvent): void {
        // Calculate mouse position in normalized device coordinates
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Raycast to check for terrain intersection
        this.raycaster.setFromCamera(this.mouse, this.camera);

        if (this.terrain) {
            const intersects = this.raycaster.intersectObject(this.terrain);
            if (intersects.length > 0) {
                const point = intersects[0].point;
                if (this.statusElement) {
                    this.statusElement.textContent = `Elevation: ${point.y.toFixed(2)}m`;
                    this.statusElement.style.display = 'block';
                }
            } else {
                this.hideStatus();
            }
        }
    }

    /**
     * Hide status display
     */
    private hideStatus(): void {
        if (this.statusElement) {
            this.statusElement.style.display = 'none';
        }
    }

    /**
     * Window resize handler
     */
    onWindowResize(): void {
        const aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera.aspect = aspect;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
    }

    /**
     * Render loop
     */
    animate(): void {
        requestAnimationFrame(() => this.animate());

        if (this.controls) {
            this.controls.update();
        }

        // Phase 5: Update water shader animation
        if (this.waterShaderManager) {
            this.waterShaderManager.update();
        }

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    /**
     * Load terrain mesh
     * @param meshData - Terrain mesh data
     */
    loadTerrain(meshData: any): void {
        // Parse mesh data and create terrain mesh
        // This would be implemented based on actual mesh format
        console.log('Loading terrain mesh...');
    }

    /**
     * Load water surface
     * @param meshData - Water mesh data
     * @param options - Water options
     */
    loadWater(meshData: WaterMeshData, options: { color?: number; opacity?: number }): void {
        console.log('Loading water surface...');
        // Create and add water mesh to scene
    }

    /**
     * Update water height
     * @param waterDepthArray - Water depth values
     */
    updateWaterHeight(waterDepthArray: Float32Array): void {
        if (!this.water) return;

        // Update water mesh vertices based on new depth
        const positions = this.water.geometry.attributes.position.array;

        for (let i = 0; i < positions.length; i += 3) {
            // positions[i] = x, positions[i+1] = y, positions[i+2] = z (height)
            // Update z based on water depth
            // This is simplified - in reality, you'd map the water depth array to vertices
        }

        this.water.geometry.attributes.position.needsUpdate = true;
    }

    /**
     * Remove water from scene
     */
    removeWater(): void {
        if (this.water) {
            this.scene.remove(this.water);
            this.water.geometry.dispose();
            if (this.water.material.dispose) {
                this.water.material.dispose();
            }
            this.water = null;
        }
    }

    /**
     * Center camera on terrain
     */
    centerCameraOnTerrain(): void {
        if (!this.terrain) {
            console.log('No terrain to center on');
            return;
        }

        const box = new THREE.Box3().setFromObject(this.terrain);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());

        console.log('Terrain center:', center);
        console.log('Terrain size:', size);

        // Calculate a better viewing distance
        // size.x = width, size.z = height variation (elevation), size.y = depth
        const maxDim = Math.max(size.x, size.y);  // Width/depth of terrain
        const heightVariation = size.z;  // Elevation range

        // Camera height: enough to see over the tallest point
        const cameraHeight = center.z + Math.max(heightVariation * 2, maxDim * 0.3);
        const distance = maxDim * 0.8;  // Horizontal distance from center

        // Position camera at an angle (isometric-like view)
        this.camera.position.set(
            center.x + distance,
            cameraHeight,
            center.y + distance  // Use Y as Z in 3D space
        );
        this.camera.lookAt(center);

        // Update controls target
        this.controls.target.copy(center);
        this.controls.update();

        console.log('Camera positioned at:', this.camera.position);
        console.log('Distance from center:', Math.sqrt(distance*distance*2));
    }

    /**
     * Reset camera to origin
     */
    resetCameraToOrigin(): void {
        console.log('Resetting camera to origin to see grid/axes');
        this.camera.position.set(200, 200, 200);
        this.camera.lookAt(0, 0, 0);
        this.controls.target.set(0, 0, 0);
        this.controls.update();
    }

    /**
     * Set camera view
     * @param view - View mode
     */
    setCameraView(view: string): void {
        if (!this.terrain) return;

        const box = new THREE.Box3().setFromObject(this.terrain);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const distance = Math.max(size.x, size.z) * 1.5;

        switch(view) {
            case 'top':
                this.camera.position.set(center.x, center.y + distance * 2, center.z);
                break;
            case 'front':
                this.camera.position.set(center.x, center.y, center.z + distance * 2);
                break;
            case 'side':
                this.camera.position.set(center.x + distance * 2, center.y, center.z);
                break;
            case 'perspective':
            default:
                this.camera.position.set(
                    center.x + distance,
                    center.y + distance,
                    center.z + distance
                );
        }

        this.camera.lookAt(center);
        this.controls.target.copy(center);
        this.controls.update();
    }

    /**
     * Get camera position
     * @returns Camera position
     */
    getCameraPosition(): THREE.Vector3 {
        return this.camera.position.clone();
    }

    /**
     * Set camera position
     * @param x - X coordinate
     * @param y - Y coordinate
     * @param z - Z coordinate
     */
    setCameraPosition(x: number, y: number, z: number): void {
        this.camera.position.set(x, y, z);
    }

    /**
     * Take screenshot
     * @returns Data URL of screenshot
     */
    takeScreenshot(): string {
        this.renderer.render(this.scene, this.camera);
        return this.canvas.toDataURL('image/png');
    }

    /**
     * Toggle terrain bounding box
     * @param enabled - Whether bounding box is visible
     */
    toggleTerrainBoundingBox(enabled: boolean): void {
        if (this.terrainBoxHelper) {
            this.terrainBoxHelper.visible = enabled;
            console.log('Terrain bounding box:', enabled ? 'shown' : 'hidden');
        }
    }

    /**
     * Dispose of resources
     */
    dispose(): void {
        // Clean up resources
        if (this.terrain) {
            this.terrain.geometry.dispose();
            this.terrain.material.dispose();
        }
        if (this.water) {
            this.water.geometry.dispose();
            if (this.water.material.dispose) {
                this.water.material.dispose();
            }
        }
        // Phase 5: Dispose water shader manager
        if (this.waterShaderManager) {
            this.waterShaderManager.dispose();
        }
        this.renderer.dispose();
    }
}