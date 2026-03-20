/**
 * Three.js 3D Map Visualization Module
 * 
 * Provides 3D terrain and water visualization using Three.js
 * with support for GIS data import and real-time updates.
 */

// Scene3D - Main 3D scene manager
class Scene3D {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas element '${canvasId}' not found`);
        }
        
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.terrain = null;
        this.water = null;
        this.waterShaderManager = null;  // Phase 5: Water shader manager
        this.lights = [];
        this.initialized = false;
        
        // Configuration
        this.config = {
            backgroundColor: 0x87CEEB,  // Sky blue
            fogDensity: 0.002,
            shadows: true,
            antialias: true
        };
        
        this.init();
    }
    
    init() {
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

    initWaterShaderManager() {
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

    setupLights() {
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
    
    setupControls() {
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 10;
        this.controls.maxDistance = 5000;
        this.controls.maxPolarAngle = Math.PI / 2 - 0.1;  // Don't go below ground
    }

    setupMouseTracking() {
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

    createStatusDisplay() {
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
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            min-width: 200px;
        `;
        this.canvas.parentElement.appendChild(this.statusElement);
    }

    onMouseMove(event) {
        // Calculate mouse position in normalized device coordinates
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        // Only raycast if terrain exists
        if (!this.terrain) {
            this.hideStatus();
            return;
        }
        
        // Update raycaster
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        // Check intersection with terrain
        const intersects = this.raycaster.intersectObject(this.terrain);
        
        if (intersects.length > 0) {
            const point = intersects[0].point;
            this.showStatus(point);
        } else {
            this.hideStatus();
        }
    }

    showStatus(point) {
        if (!this.statusElement) return;
        
        // Convert 3D coordinates back to terrain coordinates
        let terrainX = point.x;
        let terrainY = point.z;  // In 3D, Z is the horizontal plane (was Y in terrain)
        let elevation = point.y; // In 3D, Y is up (was Z in terrain)
        
        // If we have bounds info, convert to actual terrain coordinates
        if (this.terrainBounds) {
            terrainX = point.x + this.terrainBounds.centerX;
            terrainY = point.z + this.terrainBounds.centerY;
        }
        
        const elev = elevation.toFixed(2);
        
        // Check if we're in geographic coordinates (degrees)
        // Handle various CRS formats: 'EPSG:4326', '4326', or numeric
        let crs = this.terrainMetadata ? this.terrainMetadata.crs : null;
        let isGeographic = false;
        
        if (crs) {
            // Convert to string and check
            const crsStr = String(crs);
            isGeographic = crsStr.includes('4326') || crsStr.includes('EPSG:4326');
            console.log('CRS check:', crsStr, 'isGeographic:', isGeographic);
        } else {
            // Fallback: check if coordinates are in reasonable degree range (-180 to 180)
            // If terrain bounds are small (< 10 units) and not near typical meter values
            if (this.terrainBounds) {
                const rangeX = Math.abs(this.terrainBounds.maxX - this.terrainBounds.minX);
                const rangeY = Math.abs(this.terrainBounds.maxY - this.terrainBounds.minY);
                // If range is small (< 10) and coordinates are in -180 to 180 range
                if (rangeX < 10 && rangeY < 10 && 
                    this.terrainBounds.minX > -180 && this.terrainBounds.maxX < 180 &&
                    this.terrainBounds.minY > -90 && this.terrainBounds.maxY < 90) {
                    isGeographic = true;
                    console.log('Detected geographic coordinates by bounds range:', rangeX, rangeY);
                }
            }
        }
        
        if (isGeographic) {
            // Display in degrees (Lat/Lon)
            const lon = terrainX.toFixed(6);
            const lat = terrainY.toFixed(6);
            
            // Calculate approximate meters from reference point
            // 1 degree lat ≈ 111,000 meters, 1 degree lon ≈ 111,000 * cos(lat) meters
            const refLon = this.terrainMetadata && this.terrainMetadata.bounds ? this.terrainMetadata.bounds.min_x : 0;
            const refLat = this.terrainMetadata && this.terrainMetadata.bounds ? this.terrainMetadata.bounds.min_y : 0;
            
            const deltaLon = terrainX - refLon;
            const deltaLat = terrainY - refLat;
            
            // Approximate conversion (more accurate at equator)
            const metersX = Math.round(deltaLon * 111320 * Math.cos(refLat * Math.PI / 180));
            const metersY = Math.round(deltaLat * 110540);
            
            this.statusElement.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 4px; color: #4CAF50;">📍 Geographic Position</div>
                <div>Longitude: ${lon}°</div>
                <div>Latitude: ${lat}°</div>
                <div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid #444; color: #87CEEB;">
                    📏 Distance: ${metersX.toLocaleString()} m E, ${metersY.toLocaleString()} m N
                </div>
                <div style="color: #FFD700;">
                    ⛰️ Elevation: ${elev} m
                </div>
            `;
        } else {
            // Display in meters (projected coordinates)
            const coordX = terrainX.toFixed(2);
            const coordY = terrainY.toFixed(2);
            
            this.statusElement.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 4px; color: #4CAF50;">📍 Projected Position</div>
                <div>Easting: ${coordX} m</div>
                <div>Northing: ${coordY} m</div>
                <div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid #555; color: #FFD700;">
                    ⛰️ Elevation: ${elev} m
                </div>
            `;
        }
        
        this.statusElement.style.display = 'block';
    }

    hideStatus() {
        if (this.statusElement) {
            this.statusElement.style.display = 'none';
        }
    }
    
    loadTerrain(meshData, options = {}) {
        console.log('Loading terrain mesh...');
        
        // Remove existing terrain
        if (this.terrain) {
            this.scene.remove(this.terrain);
            this.terrain.geometry.dispose();
            this.terrain.material.dispose();
        }
        
        // Create geometry from BufferGeometry data
        const geometry = new THREE.BufferGeometry();
        
        // Set vertices
        const positions = new Float32Array(meshData.vertices);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        
        // Set normals if provided
        if (meshData.normals && meshData.normals.length > 0) {
            const normals = new Float32Array(meshData.normals);
            geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
        }
        
        // Set UVs if provided
        if (meshData.uvs && meshData.uvs.length > 0) {
            const uvs = new Float32Array(meshData.uvs);
            geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
        }
        
        // Set indices
        if (meshData.indices && meshData.indices.length > 0) {
            geometry.setIndex(meshData.indices);
        }
        
        geometry.computeBoundingSphere();
        
        // Debug: Check bounds
        geometry.computeBoundingBox();
        const box = geometry.boundingBox;
        const size = new THREE.Vector3();
        box.getSize(size);
        
        // Store terrain bounds for coordinate conversion
        this.terrainBounds = {
            minX: box.min.x,
            maxX: box.max.x,
            minY: box.min.z,  // In 3D, Z corresponds to terrain Y
            maxY: box.max.z,
            minElevation: box.min.y,
            maxElevation: box.max.y,
            centerX: (box.min.x + box.max.x) / 2,
            centerY: (box.min.z + box.max.z) / 2
        };
        
        console.log('Terrain bounds:', {
            min: box.min,
            max: box.max,
            size: size,
            center: box.getCenter(new THREE.Vector3()),
            terrainBounds: this.terrainBounds
        });
        
        // Update elevation legend
        this.updateElevationLegend(box.min.y, box.max.y);
        
        // Apply height-based coloring if requested
        if (options.useHeightColors !== false) {  // Default to true
            const colors = this.generateHeightColors(geometry, options.colorScheme || 'elevation');
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        }
        
        // Create material - use wireframe initially to ensure visibility
        const material = new THREE.MeshStandardMaterial({
            color: 0x8B7355,  // Earthy brown (fallback)
            roughness: 0.8,
            metalness: 0.1,
            flatShading: false,
            side: THREE.DoubleSide,  // Ensure visible from both sides
            vertexColors: options.useHeightColors !== false  // Use vertex colors if generated
        });
        
        // Create mesh
        this.terrain = new THREE.Mesh(geometry, material);
        this.terrain.castShadow = true;
        this.terrain.receiveShadow = true;
        
        // Ensure terrain is visible by checking size
        let terrainScale = 1.0;
        if (size.x < 1 || size.z < 1) {
            console.warn('Terrain very small, scaling up for visibility');
            terrainScale = 1000 / Math.max(size.x, size.z);
            this.terrain.scale.set(terrainScale, 1, terrainScale);
            
            // Update terrainBounds to reflect the scaling
            this.terrainBounds.minX *= terrainScale;
            this.terrainBounds.maxX *= terrainScale;
            this.terrainBounds.minY *= terrainScale;
            this.terrainBounds.maxY *= terrainScale;
            this.terrainBounds.centerX *= terrainScale;
            this.terrainBounds.centerY *= terrainScale;
            
            console.log('Terrain scaled by', terrainScale, '- updated bounds:', this.terrainBounds);
        }
        
        this.scene.add(this.terrain);
        
        // DEBUG: Show wireframe immediately for visibility
        console.log('Terrain added to scene at position:', this.terrain.position);
        console.log('Terrain scale:', this.terrain.scale);
        
        // Add wireframe overlay (initially hidden, toggled by checkbox)
        const wireframeGeometry = new THREE.WireframeGeometry(geometry);
        const wireframeMaterial = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 1 });
        this.terrainWireframe = new THREE.LineSegments(wireframeGeometry, wireframeMaterial);
        this.terrainWireframe.visible = false; // Hidden by default
        this.terrain.add(this.terrainWireframe);
        console.log('Added wireframe overlay (hidden by default)');
        
        // Add bounding box helper (initially hidden)
        this.terrainBoxHelper = new THREE.BoxHelper(this.terrain, 0xff0000);
        this.terrainBoxHelper.visible = false;
        this.scene.add(this.terrainBoxHelper);
        console.log('Added bounding box helper (hidden by default)');
        
        // Center camera on terrain
        this.centerCameraOnTerrain();
        
        console.log('Terrain loaded');
    }
    
    loadWater(meshData, options = {}) {
        console.log('Loading water surface...');
        console.log('Mesh data received:', {
            vertices: meshData.vertices?.length || 0,
            normals: meshData.normals?.length || 0,
            uvs: meshData.uvs?.length || 0,
            indices: meshData.indices?.length || 0
        });

        // Remove existing water using shader manager if available
        if (this.waterShaderManager && this.water) {
            this.waterShaderManager.removeWaterMesh('main');
        } else if (this.water) {
            this.scene.remove(this.water);
            this.water.geometry.dispose();
            if (this.water.material.dispose) this.water.material.dispose();
        }

        // Validate mesh data
        if (!meshData.vertices || meshData.vertices.length === 0) {
            console.error('No vertices provided for water mesh');
            return;
        }

        // Create geometry
        const geometry = new THREE.BufferGeometry();

        // Set positions
        const positions = new Float32Array(meshData.vertices);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        // Set normals
        if (meshData.normals && meshData.normals.length > 0) {
            const normals = new Float32Array(meshData.normals);
            geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
        }

        // Set UVs
        if (meshData.uvs && meshData.uvs.length > 0) {
            const uvs = new Float32Array(meshData.uvs);
            geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
        }

        // Set indices using proper BufferAttribute
        if (meshData.indices && meshData.indices.length > 0) {
            const indicesTypedArray = new Uint32Array(meshData.indices);
            geometry.setIndex(new THREE.BufferAttribute(indicesTypedArray, 1));
            console.log('Indices set:', indicesTypedArray.length);
        }

        // Phase 5: Use water shader manager for realistic rendering
        if (this.waterShaderManager) {
            // Create water mesh using shader manager
            this.water = this.waterShaderManager.createWaterMesh('main', geometry, {
                useSharedMaterial: true
            });

            // Apply preset if specified
            if (options.preset && WATER_PRESETS[options.preset]) {
                this.waterShaderManager.applyPreset(options.preset);
            }

            // Start water animation
            this.waterShaderManager.startAnimation();

            console.log('Water surface loaded with shader effects');
            
            // Add bounding box helper to debug visibility
            this.waterBoxHelper = new THREE.BoxHelper(this.water, 0x00ff00);
            this.waterBoxHelper.visible = true;
            this.scene.add(this.waterBoxHelper);
            console.log('Added water bounding box helper (green)');
        } else {
            // Fallback to basic material if shader manager not available
            const waterColor = options.color || 0x006994;
            const opacity = options.opacity || 0.7;

            const material = new THREE.MeshPhongMaterial({
                color: waterColor,
                transparent: true,
                opacity: opacity,
                shininess: 100,
                specular: 0x111111,
                side: THREE.DoubleSide
            });

            this.water = new THREE.Mesh(geometry, material);
            this.water.receiveShadow = true;
            this.scene.add(this.water);

            // Add bounding box helper to debug visibility
            this.waterBoxHelper = new THREE.BoxHelper(this.water, 0x00ff00);
            this.waterBoxHelper.visible = true;
            this.scene.add(this.waterBoxHelper);
            console.log('Water surface loaded (basic rendering) with bounding box');
        }
        
        // Log water position for debugging
        geometry.computeBoundingBox();
        const waterBox = geometry.boundingBox;
        console.log('Water bounding box:', {
            min: waterBox.min,
            max: waterBox.max,
            center: waterBox.getCenter(new THREE.Vector3())
        });
    }

    setWaterPreset(presetName) {
        if (this.waterShaderManager) {
            this.waterShaderManager.applyPreset(presetName);
            console.log(`Applied water preset: ${presetName}`);
        }
    }

    setWaterWaveParams(params) {
        if (this.waterShaderManager) {
            this.waterShaderManager.setWaveParameters(params);
        }
    }

    toggleWaterAnimation(enabled) {
        if (this.waterShaderManager) {
            if (enabled) {
                this.waterShaderManager.startAnimation();
            } else {
                this.waterShaderManager.stopAnimation();
            }
        }
    }

    removeWater() {
        console.log('Removing water from scene...');
        
        if (this.waterShaderManager && this.water) {
            this.waterShaderManager.removeWaterMesh('main');
        } else if (this.water) {
            this.scene.remove(this.water);
            this.water.geometry.dispose();
            if (this.water.material.dispose) {
                this.water.material.dispose();
            }
            this.water = null;
        }
        
        this.water = null;
        console.log('Water removed');
    }

    updateElevationLegend(minElevation, maxElevation) {
        const legendMin = document.getElementById('legend-min');
        const legendMax = document.getElementById('legend-max');
        
        if (legendMin && legendMax) {
            // Round to reasonable precision
            const min = Math.round(minElevation * 10) / 10;
            const max = Math.round(maxElevation * 10) / 10;
            
            legendMin.textContent = min + 'm';
            legendMax.textContent = max + 'm';
            
            console.log('Elevation legend updated:', min + 'm to ' + max + 'm');
        }
    }

    generateHeightColors(geometry, scheme = 'elevation') {
        const positions = geometry.attributes.position.array;
        const colors = new Float32Array(positions.length);
        
        // Find min/max height (Y coordinate)
        let minY = Infinity;
        let maxY = -Infinity;
        for (let i = 1; i < positions.length; i += 3) {
            const y = positions[i];
            minY = Math.min(minY, y);
            maxY = Math.max(maxY, y);
        }
        
        const heightRange = maxY - minY || 1;
        
        // Color schemes
        const schemes = {
            elevation: (t) => {
                // Blue (low) -> Green (mid) -> Brown (high) -> White (peak)
                if (t < 0.25) return [0.0, 0.2 + t * 2, 0.8 - t * 2];  // Deep blue to light blue
                if (t < 0.5) return [0.0, 0.7, 0.4 - (t - 0.25) * 1.6];  // Blue to green
                if (t < 0.75) return [0.4 + (t - 0.5) * 2, 0.7 - (t - 0.5) * 1.2, 0.0];  // Green to brown
                return [0.9 + (t - 0.75) * 0.4, 0.4 + (t - 0.75) * 0.4, 0.2 + (t - 0.75) * 2];  // Brown to white
            },
            heatmap: (t) => {
                // Black -> Blue -> Cyan -> Green -> Yellow -> Red -> White
                if (t < 0.15) return [0, 0, t / 0.15];
                if (t < 0.3) return [0, (t - 0.15) / 0.15, 1];
                if (t < 0.45) return [0, 1, 1 - (t - 0.3) / 0.15];
                if (t < 0.6) return [(t - 0.45) / 0.15, 1, 0];
                if (t < 0.75) return [1, 1 - (t - 0.6) / 0.15, 0];
                if (t < 0.9) return [1, 0, (t - 0.75) / 0.15];
                return [1, (t - 0.9) / 0.1, (t - 0.9) / 0.1];
            },
            grayscale: (t) => {
                // Black to white
                const v = t * 0.8 + 0.2;
                return [v, v, v];
            },
            solid: (t) => {
                // Earthy brown
                return [0.545, 0.451, 0.333];
            }
        };
        
        const colorFunc = schemes[scheme] || schemes.elevation;
        
        for (let i = 0; i < positions.length; i += 3) {
            const y = positions[i + 1];
            const t = Math.max(0, Math.min(1, (y - minY) / heightRange));
            const [r, g, b] = colorFunc(t);
            colors[i] = r;
            colors[i + 1] = g;
            colors[i + 2] = b;
        }
        
        console.log(`Generated ${scheme} height colors for ${positions.length / 3} vertices`);
        return colors;
    }

    toggleTerrainWireframe(enabled) {
        if (this.terrainWireframe) {
            this.terrainWireframe.visible = enabled;
            console.log('Terrain wireframe:', enabled ? 'shown' : 'hidden');
        }
    }

    toggleTerrainVisible(visible) {
        if (this.terrain) {
            this.terrain.visible = visible;
            if (this.terrainWireframe) this.terrainWireframe.visible = visible && this.terrainWireframe.visible;
            if (this.terrainBoxHelper) this.terrainBoxHelper.visible = visible && this.terrainBoxHelper.visible;
            console.log('Terrain visible:', visible);
        }
    }

    toggleTerrainBoundingBox(enabled) {
        if (this.terrainBoxHelper) {
            this.terrainBoxHelper.visible = enabled;
            console.log('Terrain bounding box:', enabled ? 'shown' : 'hidden');
        }
    }

    updateWaterHeight(waterDepthArray) {
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
    
    centerCameraOnTerrain() {
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
    
    resetCameraToOrigin() {
        console.log('Resetting camera to origin to see grid/axes');
        this.camera.position.set(200, 200, 200);
        this.camera.lookAt(0, 0, 0);
        this.controls.target.set(0, 0, 0);
        this.controls.update();
    }
    
    setCameraView(view) {
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
    
    onWindowResize() {
        const aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera.aspect = aspect;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
    }
    
    animate() {
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
    
    dispose() {
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
    
    // API methods for external control
    getCameraPosition() {
        return this.camera.position.clone();
    }
    
    setCameraPosition(x, y, z) {
        this.camera.position.set(x, y, z);
    }
    
    takeScreenshot() {
        this.renderer.render(this.scene, this.camera);
        return this.canvas.toDataURL('image/png');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Scene3D };
}
// Debug helper - add this at the end of the file
// You can call this from console: window.scene3D.debugScene()
Scene3D.prototype.debugScene = function() {
    console.log('=== SCENE DEBUG ===');
    console.log('Camera position:', this.camera.position);
    console.log('Camera looking at:', this.controls.target);
    console.log('Scene children count:', this.scene.children.length);
    console.log('Terrain:', this.terrain ? 'Present' : 'Not present');
    
    // List all objects in scene
    this.scene.children.forEach((child, i) => {
        console.log(`Object ${i}:`, child.type, child.name || '');
        if (child.geometry) {
            console.log('  - Vertices:', child.geometry.attributes.position?.count || 0);
        }
    });
    
    // Force camera to look at origin
    console.log('Resetting camera to see grid...');
    this.camera.position.set(500, 500, 500);
    this.camera.lookAt(0, 0, 0);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
    
    // Add a visible test cube at origin
    const testGeometry = new THREE.BoxGeometry(50, 50, 50);
    const testMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
    const testCube = new THREE.Mesh(testGeometry, testMaterial);
    testCube.position.set(0, 25, 0);
    this.scene.add(testCube);
    console.log('Added red test cube at origin');
};
