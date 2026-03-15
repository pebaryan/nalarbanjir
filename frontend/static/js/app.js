/**
 * Flood Prediction World Model - Main Application Script
 * 
 * This script provides the core functionality for the web-based user interface,
 * including navigation, data management, and user interactions.
 */

// Application State
const AppState = {
    currentSection: 'dashboard',
    simulationRunning: false,
    lastUpdate: Date.now(),
    userPreferences: {
        theme: 'light',
        notifications: true,
        autoRefresh: true
    }
};

// API Configuration
const API_CONFIG = {
    BASE_URL: '/api',
    ENDPOINTS: {
        simulate: '/simulate',
        state: '/state',
        terrain: '/terrain',
        predict: '/predict',
        history: '/history'
    },
    WS_URL: '/ws'
};

// Stub classes for modules that will be loaded separately
// These provide the interface expected by the navigation handler
class Simulation {
    static initialize() {
        console.log('Simulation section initialized');
        // Use window.simulationManager if available
        if (window.simulationManager) {
            console.log('Using simulationManager');
        }
    }
    
    static togglePlayPause() {
        console.log('Toggle play/pause');
        alert('Play/Pause functionality coming soon!');
    }
    
    static resetSimulation() {
        console.log('Reset simulation');
        alert('Reset functionality coming soon!');
    }
    
    static updateTimeSlider(value) {
        console.log('Time slider updated:', value);
    }
}

class Visualization {
    static initialize() {
        console.log('Visualization section initialized');
        if (window.visualizationManager) {
            console.log('Using visualizationManager');
        }
    }
}

class Analytics {
    static initialize() {
        console.log('Analytics section initialized');
        if (window.analyticsManager) {
            console.log('Using analyticsManager');
        }
    }
}

class Settings {
    static initialize() {
        console.log('Settings section initialized');
    }
}

// Navigation Handler
class NavigationHandler {
    constructor() {
        this.navLinks = document.querySelectorAll('.nav-link');
        this.sections = document.querySelectorAll('.section');
        this.init();
    }

    init() {
        this.attachEventListeners();
        this.updateActiveLink('dashboard');
    }

    attachEventListeners() {
        this.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                const sectionId = e.target.getAttribute('href').substring(1);
                this.switchSection(sectionId);
            });
        });
    }

    switchSection(sectionId) {
        // Update active section
        this.sections.forEach(section => {
            section.classList.remove('active');
            if (section.id === sectionId) {
                section.classList.add('active');
            }
        });

        // Update active navigation link
        this.updateActiveLink(sectionId);

        // Store current section
        AppState.currentSection = sectionId;

        // Trigger section-specific updates
        this.handleSectionChange(sectionId);
    }

    updateActiveLink(sectionId) {
        this.navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href').substring(1) === sectionId) {
                link.classList.add('active');
            }
        });
    }

    handleSectionChange(sectionId) {
        // Trigger section-specific handlers
        switch (sectionId) {
            case 'dashboard':
                Dashboard.initialize();
                break;
            case '3d-view':
                Map3D.initialize();
                break;
            case 'simulation':
                Simulation.initialize();
                break;
            case 'visualization':
                Visualization.initialize();
                break;
            case 'analytics':
                Analytics.initialize();
                break;
            case 'settings':
                Settings.initialize();
                break;
        }
    }
}

// 3D Map View Handler
class Map3D {
    static initialize() {
        console.log('3D Map section initialized');
        
        // Ensure the 3D canvas is properly sized
        this.resizeCanvas();
        
        // Trigger window resize event to update Three.js renderer
        window.dispatchEvent(new Event('resize'));
        
        // If scene3D exists, update its controls
        if (window.scene3D) {
            console.log('Updating 3D scene display');
            window.scene3D.onWindowResize();
        } else {
            console.warn('Scene3D not initialized yet');
        }
        
        this.bindEvents();
    }
    
    static resizeCanvas() {
        const canvas = document.getElementById('threejs-canvas');
        if (canvas) {
            const container = canvas.parentElement;
            if (container) {
                // Force canvas to fill container
                canvas.style.width = '100%';
                canvas.style.height = '100%';
                console.log('3D canvas resized to:', container.clientWidth, 'x', container.clientHeight);
            }
        }
    }
    
    static bindEvents() {
        // Upload terrain button
        document.getElementById('upload-terrain-btn')?.addEventListener('click', () => {
            this.showUploadDialog();
        });
        
        // Reset view button
        document.getElementById('reset-view-btn')?.addEventListener('click', () => {
            this.resetView();
        });
        
        // View mode selector
        document.getElementById('view-mode-select')?.addEventListener('change', (e) => {
            this.changeViewMode(e.target.value);
        });
        
        // Terrain controls
        document.getElementById('terrain-wireframe')?.addEventListener('change', (e) => {
            this.toggleTerrainWireframe(e.target.checked);
        });
        
        document.getElementById('terrain-visible')?.addEventListener('change', (e) => {
            this.toggleTerrainVisible(e.target.checked);
        });
        
        document.getElementById('terrain-color-scheme')?.addEventListener('change', (e) => {
            this.changeTerrainColorScheme(e.target.value);
        });
        
        // Water controls
        document.getElementById('water-visible')?.addEventListener('change', (e) => {
            this.toggleWaterVisible(e.target.checked);
        });
        
        document.getElementById('water-level')?.addEventListener('input', (e) => {
            document.getElementById('water-level-value').textContent = e.target.value + ' m';
        });
        
        document.getElementById('add-water-btn')?.addEventListener('click', () => {
            const level = parseFloat(document.getElementById('water-level')?.value || 10);
            this.addWaterAtLevel(level);
        });
        
        document.getElementById('remove-water-btn')?.addEventListener('click', () => {
            this.removeWater();
        });
        
        // Window resize handler
        window.addEventListener('resize', () => {
            this.resizeCanvas();
        });
        
        // File upload input
        const fileInput = document.getElementById('gis-file-input');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                this.handleFileUpload(e);
            });
        }
        
        // Upload zone click handler
        const uploadZone = document.getElementById('gis-upload-zone');
        if (uploadZone) {
            uploadZone.addEventListener('click', () => {
                fileInput?.click();
            });
            
            // Drag and drop handlers
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadZone.style.background = '#e5e7eb';
            });
            
            uploadZone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadZone.style.background = '';
            });
            
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadZone.style.background = '';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    // Create a proper event-like object with files
                    const dropEvent = {
                        target: {
                            files: files
                        }
                    };
                    this.handleFileUpload(dropEvent);
                }
            });
        }
    }
    
    static showUploadDialog() {
        const uploadSection = document.querySelector('.file-upload-section');
        if (uploadSection) {
            uploadSection.style.display = 'block';
        }
    }
    
    static resetView() {
        if (window.scene3D) {
            window.scene3D.setCameraView('perspective');
            console.log('View reset to perspective');
        }
    }
    
    static changeViewMode(mode) {
        if (window.scene3D) {
            window.scene3D.setCameraView(mode);
            console.log('View mode changed to:', mode);
        }
    }
    
    static toggleTerrainWireframe(enabled) {
        if (window.scene3D && window.scene3D.terrain) {
            window.scene3D.terrain.material.wireframe = enabled;
        }
    }
    
    static toggleTerrainVisible(visible) {
        if (window.scene3D && window.scene3D.terrain) {
            window.scene3D.terrain.visible = visible;
        }
    }
    
    static changeTerrainColorScheme(scheme) {
        console.log('Changing terrain color scheme to:', scheme);
        if (window.scene3D && window.scene3D.terrain) {
            // Reload terrain with new color scheme
            const currentMesh = window.scene3D.terrain;
            const geometry = currentMesh.geometry;
            
            // Generate new colors
            const colors = window.scene3D.generateHeightColors(geometry, scheme);
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            
            // Update material to use vertex colors
            currentMesh.material.vertexColors = true;
            currentMesh.material.needsUpdate = true;
            
            console.log('Color scheme updated to:', scheme);
        }
    }
    
    static toggleWaterVisible(visible) {
        if (window.scene3D && window.scene3D.water) {
            window.scene3D.water.visible = visible;
        }
    }
    
    static updateWaterOpacity(opacity) {
        if (window.scene3D && window.scene3D.water) {
            window.scene3D.water.material.opacity = opacity / 100;
        }
    }

    static addWaterAtLevel(level) {
        console.log('Adding water at level:', level, 'm');
        if (window.scene3D && window.scene3D.terrain) {
            // Get terrain bounds to match water extent
            const bounds = window.scene3D.terrainBounds;
            if (!bounds) {
                console.error('No terrain bounds available');
                return;
            }
            
            // Calculate terrain dimensions
            const width = Math.abs(bounds.maxX - bounds.minX);
            const depth = Math.abs(bounds.maxY - bounds.minY);
            const centerX = (bounds.minX + bounds.maxX) / 2;
            const centerZ = (bounds.minY + bounds.maxY) / 2;
            
            console.log('Creating water matching terrain extent:', {
                width: width,
                depth: depth,
                centerX: centerX,
                centerZ: centerZ,
                level: level,
                terrainMinElevation: bounds.minElevation,
                terrainMaxElevation: bounds.maxElevation
            });
            
            // Validate water level is within reasonable range
            if (level < bounds.minElevation || level > bounds.maxElevation + 50) {
                console.warn(`Water level ${level}m is outside terrain elevation range (${bounds.minElevation}-${bounds.maxElevation}m). Water may not be visible.`);
            }
            
            // Create water plane matching terrain extent
            const geometry = new THREE.PlaneGeometry(width, depth, 50, 50);
            geometry.rotateX(-Math.PI / 2); // Make it horizontal
            
            // Position at water level and terrain center
            // Note: In Three.js Y is up, so level goes to Y coordinate
            geometry.translate(centerX, level, centerZ);
            
            console.log('Water plane positioned at:', {x: centerX, y: level, z: centerZ});
            
            // Compute vertex normals for proper lighting
            geometry.computeVertexNormals();
            
            // Clone arrays to avoid reference issues and ensure we have actual data
            const vertices = new Float32Array(geometry.attributes.position.array);
            const normals = geometry.attributes.normal ? new Float32Array(geometry.attributes.normal.array) : new Float32Array(vertices.length);
            
            // UVs are required for the shader - generate if not present
            let uvs;
            if (geometry.attributes.uv && geometry.attributes.uv.array.length > 0) {
                uvs = new Float32Array(geometry.attributes.uv.array);
            } else {
                // Generate UVs for a grid (51x51 vertices for 50 segments)
                const segments = 50;
                const uvArray = [];
                for (let i = 0; i <= segments; i++) {
                    for (let j = 0; j <= segments; j++) {
                        uvArray.push(j / segments, i / segments);
                    }
                }
                uvs = new Float32Array(uvArray);
            }
            
            // PlaneGeometry in newer Three.js doesn't use indices by default
            // We need to generate them manually for indexed rendering
            let indices;
            if (geometry.index && geometry.index.array && geometry.index.array.length > 0) {
                indices = new Uint32Array(geometry.index.array);
            } else {
                // Generate indices for a grid (50x50 segments = 51x51 vertices)
                const segments = 50;
                const indicesArray = [];
                for (let i = 0; i < segments; i++) {
                    for (let j = 0; j < segments; j++) {
                        const a = i * (segments + 1) + j;
                        const b = a + 1;
                        const c = a + segments + 1;
                        const d = c + 1;
                        // Two triangles per quad
                        indicesArray.push(a, b, c);
                        indicesArray.push(b, d, c);
                    }
                }
                indices = new Uint32Array(indicesArray);
            }
            
            // Validate all arrays have data
            if (vertices.length === 0) {
                console.error('No vertices generated!');
                return;
            }
            if (uvs.length === 0) {
                console.error('No UVs generated!');
                return;
            }
            if (indices.length === 0) {
                console.error('No indices generated!');
                return;
            }
            
            console.log('Water geometry prepared:', {
                vertices: vertices.length,
                normals: normals.length,
                uvs: uvs.length,
                indices: indices.length
            });
            
            // Create water mesh
            window.scene3D.loadWater({
                vertices: vertices,
                normals: normals,
                uvs: uvs,
                indices: indices
            }, {
                opacity: parseFloat(document.getElementById('water-opacity')?.value || 70),
                preset: 'calm'
            });
            
            console.log('Water added at elevation:', level, 'm');
            
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = `<p style="color: blue;">💧 Water added at ${level}m elevation</p>`;
            }
        } else {
            console.warn('No terrain loaded - cannot add water');
            alert('Please load terrain first before adding water');
        }
    }

    static removeWater() {
        console.log('Removing water');
        if (window.scene3D) {
            window.scene3D.removeWater();
            
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = '<p style="color: gray;">🚫 Water removed</p>';
            }
        }
    }

    static handleFileUpload(event) {
        try {
            if (!event || !event.target || !event.target.files) {
                console.error('Invalid upload event:', event);
                return;
            }
            
            const file = event.target.files[0];
            if (!file) {
                console.log('No file selected');
                return;
            }
            
            console.log('File selected:', file.name);
            
            // Show progress
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = '<p>Uploading...</p>';
            }
            
            // Upload file
            this.uploadFile(file);
        } catch (error) {
            console.error('Error in handleFileUpload:', error);
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = `<p style="color: red;">✗ Upload error: ${error.message}</p>`;
            }
        }
    }
    
    static async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/gis/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Upload failed: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Upload successful:', result);
            
            // Generate terrain mesh
            if (result.file_id && result.type === 'raster') {
                console.log('Starting mesh generation for file:', result.file_id);
                const width = result.dimensions?.width || 0;
                const height = result.dimensions?.height || 0;
                const totalPixels = width * height;
                
                // Warn about large files
                if (totalPixels > 1000000) {
                    const progressDiv = document.getElementById('upload-progress');
                    if (progressDiv) {
                        progressDiv.innerHTML = `<p style="color: orange;">⚠️ Large file detected (${width}x${height} = ${totalPixels.toLocaleString()} pixels)</p><p style="font-size: 12px;">This may take several minutes to process...</p>`;
                    }
                }
                
                this.generateTerrainMesh(result.file_id).catch(err => {
                    console.error('Mesh generation failed:', err);
                });
            }
            
            // Update progress
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = '<p style="color: green;">✓ Upload successful!</p>';
            }
            
        } catch (error) {
            console.error('Upload error:', error);
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = `<p style="color: red;">✗ Error: ${error.message}</p>`;
            }
        }
    }
    
    static async generateTerrainMesh(fileId) {
        console.log('generateTerrainMesh called for fileId:', fileId);
        const progressDiv = document.getElementById('upload-progress');
        if (progressDiv) {
            progressDiv.innerHTML = '<p>Generating mesh... <span id="mesh-progress">0%</span></p><p style="font-size: 12px; color: #666;">Large files may take 1-2 minutes to tile</p>';
        }
        
        try {
            console.log('Sending mesh generation request...');
            
            // Create AbortController for timeout - 2 minutes for large files
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                controller.abort();
                console.error('Mesh generation timeout after 2 minutes');
            }, 120000); // 2 minute timeout for tiling
            
            const response = await fetch('/api/gis/generate_terrain_mesh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_id: fileId,
                    simplification: 0.95, // More aggressive for large files
                    z_scale: 1.0
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            console.log('Mesh generation response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Mesh generation error response:', errorText);
                throw new Error(`Mesh generation failed: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Mesh generated:', result);
            
            // Check if this is a proxy response (large file with immediate preview)
            if (result.status === 'proxy' && result.use_proxy) {
                console.log('Large file detected, loading proxy mesh immediately');
                
                if (progressDiv) {
                    progressDiv.innerHTML = `<p style="color: blue;">📦 Large DTM (${result.total_pixels?.toLocaleString()} pixels)</p><p>Loading preview...</p>`;
                }
                
                // Load the proxy mesh immediately
                try {
                    await this.loadMeshData(result.proxy_mesh_id);
                    
                    // Store metadata for coordinate display
                    if (window.scene3D && result.crs && result.bounds) {
                        window.scene3D.terrainMetadata = {
                            crs: result.crs,
                            bounds: result.bounds
                        };
                        console.log('Stored terrain metadata:', window.scene3D.terrainMetadata);
                    }
                    
                    if (progressDiv) {
                        progressDiv.innerHTML = `<p style="color: green;">✓ Preview loaded! Generating ${result.estimated_tiles} detailed tiles in background...</p><p style="font-size: 12px;">Navigate freely while detailed tiles load</p>`;
                    }
                    
                    // Poll for tiling progress
                    this.pollTilingProgress(result.task_id, progressDiv);
                    
                } catch (error) {
                    console.error('Proxy mesh load failed:', error);
                    if (progressDiv) {
                        progressDiv.innerHTML = `<p style="color: red;">✗ Failed to load preview</p>`;
                    }
                }
                
                return;
            }
            
            // Check if this is a tiled response (legacy - should not happen now)
            if (result.status === 'tiled' && result.use_streaming) {
                console.log('Legacy tiled response - using proxy instead');
                if (progressDiv) {
                    progressDiv.innerHTML = `<p style="color: orange;">⏳ Processing large file...</p>`;
                }
                return;
            }
            
            // Check if mesh is too large for browser
            const vertexCount = result.metadata?.vertex_count || 0;
            if (vertexCount > 500000) {
                console.warn(`Mesh has ${vertexCount} vertices - this may be too large for smooth rendering`);
                if (progressDiv) {
                    progressDiv.innerHTML = `<p style="color: orange;">⚠️ Large mesh (${vertexCount.toLocaleString()} vertices) - may be slow to render</p>`;
                }
            }
            
            // Load mesh data
            if (result.mesh_id) {
                console.log('Loading mesh data for:', result.mesh_id);
                await this.loadMeshData(result.mesh_id);
            } else {
                console.error('No mesh_id in result');
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.error('Mesh generation timeout after 2 minutes');
                if (progressDiv) {
                    progressDiv.innerHTML = '<p style="color: orange;">⏳ Processing large file... Please wait or try a smaller DTM file</p><p style="font-size: 12px;">Files over 500k pixels are automatically tiled which takes time</p>';
                }
            } else {
                console.error('Mesh generation error:', error);
                if (progressDiv) {
                    progressDiv.innerHTML = `<p style="color: red;">✗ Mesh error: ${error.message}</p>`;
                }
            }
            throw error;
        }
    }

    static async pollTilingProgress(taskId, progressDiv) {
        // Poll every 5 seconds for tiling progress
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/gis/tiling-progress/${taskId}`);
                const progress = await response.json();
                
                if (progressDiv) {
                    if (progress.status === 'completed') {
                        clearInterval(pollInterval);
                        progressDiv.innerHTML = `<p style="color: green;">✓ Detailed tiling complete! (${progress.completed_tiles} tiles)</p>`;
                    } else if (progress.status === 'processing') {
                        const percent = Math.round((progress.completed_tiles / progress.total_tiles) * 100);
                        progressDiv.innerHTML = `<p style="color: blue;">⏳ Generating detailed tiles: ${progress.completed_tiles}/${progress.total_tiles} (${percent}%)</p>`;
                    } else if (progress.status === 'error') {
                        clearInterval(pollInterval);
                        progressDiv.innerHTML = `<p style="color: red;">✗ Tiling error: ${progress.message}</p>`;
                    }
                }
            } catch (error) {
                console.error('Progress poll error:', error);
            }
        }, 5000); // Poll every 5 seconds
    }
    
    static async loadMeshData(meshId) {
        try {
            const response = await fetch(`/api/gis/mesh/${meshId}`);
            
            if (!response.ok) {
                throw new Error(`Failed to load mesh: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Mesh data loaded:', result);
            
            // Convert Three.js BufferGeometry format to expected format
            let meshData;
            if (result.threejs_geometry) {
                const geo = result.threejs_geometry;
                // Handle BufferGeometry format
                if (geo.data && geo.data.attributes) {
                    meshData = {
                        vertices: geo.data.attributes.position?.array || [],
                        indices: geo.data.index?.array || [],
                        normals: geo.data.attributes.normal?.array || [],
                        uvs: geo.data.attributes.uv?.array || []
                    };
                } else {
                    // Fallback to old format
                    meshData = result.threejs_geometry;
                }
            }
            
            // Load into Three.js scene
            if (window.scene3D && meshData) {
                console.log('Loading terrain with', meshData.vertices.length, 'vertices');
                window.scene3D.loadTerrain(meshData);
                
                // Update scene info
                document.getElementById('vertex-count').textContent = 
                    result.metadata?.vertex_count || '0';
                document.getElementById('face-count').textContent = 
                    result.metadata?.face_count || '0';
                
                const progressDiv = document.getElementById('upload-progress');
                if (progressDiv) {
                    progressDiv.innerHTML = '<p style="color: green;">✓ Terrain loaded!</p>';
                }
            } else {
                console.error('Cannot load mesh: scene3D or meshData missing');
                const progressDiv = document.getElementById('upload-progress');
                if (progressDiv) {
                    progressDiv.innerHTML = '<p style="color: red;">✗ Failed to load terrain</p>';
                }
            }
            
        } catch (error) {
            console.error('Load mesh error:', error);
            const progressDiv = document.getElementById('upload-progress');
            if (progressDiv) {
                progressDiv.innerHTML = `<p style="color: red;">✗ Error: ${error.message}</p>`;
            }
        }
    }
}

// Dashboard Handler
class Dashboard {
    static initialize() {
        this.bindEvents();
        this.loadDashboardData();
    }

    static bindEvents() {
        // Button event bindings
        document.getElementById('export-btn')?.addEventListener('click', () => {
            this.exportData();
        });

        document.getElementById('refresh-btn')?.addEventListener('click', () => {
            this.refreshDashboard();
        });

        document.getElementById('settings-btn')?.addEventListener('click', () => {
            this.openSettings();
        });

        // Canvas event bindings
        const waterCanvas = document.getElementById('water-surface-canvas');
        if (waterCanvas) {
            waterCanvas.addEventListener('click', (e) => {
                this.handleCanvasClick(e, 'water');
            });
        }

        const flowCanvas = document.getElementById('flow-vectors-canvas');
        if (flowCanvas) {
            flowCanvas.addEventListener('click', (e) => {
                this.handleCanvasClick(e, 'flow');
            });
        }
    }

    static loadDashboardData() {
        // Load initial dashboard data
        this.updateMetrics();
        this.renderRiskAssessment();
        this.updateSimulationControls();
    }

    static updateMetrics() {
        // Update dashboard metrics
        const metrics = {
            'avg-depth': '1.5m',
            'max-depth': '3.2m',
            'surface-area': '10,000m²',
            'flow-velocity': '0.45 m/s',
            'flow-direction': 'NE',
            'flow-rate': '125 m³/s'
        };

        Object.entries(metrics).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });
    }

    static renderRiskAssessment() {
        // Render risk assessment visualization
        const riskMetrics = document.getElementById('risk-metrics');
        if (riskMetrics) {
            riskMetrics.innerHTML = `
                <div class="risk-indicators">
                    <div class="indicator">
                        <span class="indicator-label">Flood Risk Index</span>
                        <span class="indicator-value">0.75</span>
                    </div>
                    <div class="indicator">
                        <span class="indicator-label">Response Time</span>
                        <span class="indicator-value">85ms</span>
                    </div>
                    <div class="indicator">
                        <span class="indicator-label">Data Freshness</span>
                        <span class="indicator-value">Real-time</span>
                    </div>
                </div>
            `;
        }
    }

    static updateSimulationControls() {
        // Update simulation control states
        const playPauseBtn = document.getElementById('play-pause');
        if (playPauseBtn) {
            playPauseBtn.addEventListener('click', () => {
                Simulation.togglePlayPause();
            });
        }

        const resetBtn = document.getElementById('reset-sim');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                Simulation.resetSimulation();
            });
        }

        const timeSlider = document.getElementById('time-slider');
        if (timeSlider) {
            timeSlider.addEventListener('input', (e) => {
                Simulation.updateTimeSlider(e.target.value);
            });
        }
    }

    static async exportData() {
        try {
            const response = await fetch(`${API_CONFIG.BASE_URL}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Data exported:', data);
                this.showNotification('Data exported successfully', 'success');
            }
        } catch (error) {
            console.error('Export error:', error);
            this.showNotification('Export failed', 'error');
        }
    }

    static async refreshDashboard() {
        try {
            // Show loading state
            document.body.classList.add('loading');

            // Refresh dashboard data
            const response = await fetch(`${API_CONFIG.BASE_URL}/state`);
            const data = await response.json();

            // Update dashboard with new data
            this.updateFromState(data);

            // Hide loading state
            document.body.classList.remove('loading');

            this.showNotification('Dashboard refreshed', 'success');
        } catch (error) {
            console.error('Refresh error:', error);
            this.showNotification('Refresh failed', 'error');
        }
    }

    static updateFromState(state) {
        // Update various dashboard components with new state
        if (state.physics) {
            this.updateWaterSurface(state.physics.state);
        }

        if (state.terrain) {
            this.updateTerrainData(state.terrain);
        }

        if (state.ml) {
            this.updateMLInsights(state.ml);
        }
    }

    static updateWaterSurface(waterState) {
        // Update water surface visualization
        const waterCanvas = document.getElementById('water-surface-canvas');
        if (waterCanvas) {
            // Update canvas with new water state
            const ctx = waterCanvas.getContext('2d');
            this.renderWaterSurface(ctx, waterState);
        }
    }

    static renderWaterSurface(ctx, waterState) {
        // Render water surface visualization
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

        // Draw water surface
        ctx.fillStyle = '#3b82f6';
        ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

        // Add water surface details
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.beginPath();
        ctx.arc(100, 100, 50, 0, 2 * Math.PI);
        ctx.fill();
    }

    static updateTerrainData(terrainData) {
        // Update terrain data display
        const terrainCard = document.querySelector('.flood-risk-card');
        if (terrainCard) {
            // Update terrain metrics
            const metrics = terrainCard.querySelectorAll('.metric-value');
            if (metrics.length >= 3) {
                metrics[0].textContent = `${terrainData.elevation.mean}m`;
                metrics[1].textContent = `${terrainData.permeability.mean}`;
                metrics[2].textContent = `${terrainData.total_area}m²`;
            }
        }
    }

    static updateMLInsights(mlData) {
        // Update ML insights display
        const insightsPanel = document.getElementById('insights-panel');
        if (insightsPanel) {
            insightsPanel.innerHTML = `
                <div class="insights-content">
                    <h4>ML Insights</h4>
                    <div class="insight-item">
                        <span class="insight-type">Prediction</span>
                        <span class="insight-value">${mlData.model_type}</span>
                    </div>
                    <div class="insight-item">
                        <span class="insight-type">Confidence</span>
                        <span class="insight-value">${mlData.training.quality}</span>
                    </div>
                </div>
            `;
        }
    }

    static handleCanvasClick(event, canvasType) {
        // Handle canvas click events
        const x = event.offsetX;
        const y = event.offsetY;

        console.log(`${canvasType} canvas clicked at (${x}, ${y})`);

        // Get data at click location
        const dataPoint = this.getCanvasDataPoint(canvasType, x, y);

        if (dataPoint) {
            this.showDataPointDetails(dataPoint);
        }
    }

    static getCanvasDataPoint(canvasType, x, y) {
        // Get data point at clicked location
        return {
            type: canvasType,
            location: { x, y },
            timestamp: Date.now(),
            data: this.extractDataFromCanvas(canvasType, x, y)
        };
    }

    static extractDataFromCanvas(canvasType, x, y) {
        // Extract relevant data from canvas based on type
        const data = {
            waterSurface: this.extractWaterData(x, y),
            flowVectors: this.extractFlowData(x, y),
            floodZones: this.extractFloodData(x, y)
        };

        return data[canvasType] || null;
    }

    static extractWaterData(x, y) {
        // Extract water surface data
        return {
            depth: this.calculateDepth(x, y),
            velocity: this.calculateVelocity(x, y),
            quality: this.assessWaterQuality(x, y)
        };
    }

    static calculateDepth(x, y) {
        // Calculate water depth based on position
        return 1.5 + (Math.sin(x / 100) * Math.cos(y / 100)) * 2;
    }

    static calculateVelocity(x, y) {
        // Calculate water velocity based on position
        return Math.sqrt(Math.pow(Math.sin(x / 50), 2) + Math.pow(Math.cos(y / 50), 2));
    }

    static assessWaterQuality(x, y) {
        // Assess water quality based on position
        const qualityScore = (x + y) / 200;
        return qualityScore > 0.7 ? 'excellent' : qualityScore > 0.5 ? 'good' : 'moderate';
    }

    static showDataPointDetails(dataPoint) {
        // Display details of clicked data point
        console.log('Data Point Details:', dataPoint);

        // Show notification
        this.showNotification(`Data point details for ${dataPoint.type}`, 'info');
    }

    static openSettings() {
        // Open settings panel
        const settingsPanel = document.getElementById('settings-panel');
        if (settingsPanel) {
            settingsPanel.classList.toggle('active');
        } else {
            this.createSettingsPanel();
        }
    }

    static createSettingsPanel() {
        // Create settings panel if not exists
        const panel = document.createElement('div');
        panel.id = 'settings-panel';
        panel.className = 'settings-panel';
        panel.innerHTML = `
            <div class="settings-content">
                <h3>Settings</h3>
                <div class="settings-section">
                    <h4>Display Preferences</h4>
                    <label>
                        <input type="checkbox" checked> Light Theme
                    </label>
                    <label>
                        <input type="checkbox" checked> Auto-refresh
                    </label>
                </div>
                <div class="settings-section">
                    <h4>Notifications</h4>
                    <label>
                        <input type="checkbox" checked> Email Alerts
                    </label>
                    <label>
                        <input type="checkbox"> Push Notifications
                    </label>
                </div>
                <button class="btn btn-primary">Save Settings</button>
            </div>
        `;

        document.body.appendChild(panel);
    }

    static showNotification(message, type = 'info') {
        // Show notification message
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // Auto-remove notification after delay
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    // Initialize navigation
    new NavigationHandler();

    // Initialize dashboard
    Dashboard.initialize();

    // Initialize simulation (defined in simulation.js)
    if (window.simulationManager) {
        console.log('Simulation manager ready');
    }

    // Initialize visualization (defined in visualization.js)
    if (window.visualizationManager) {
        console.log('Visualization manager ready');
    }

    // Initialize analytics (defined in analytics.js)
    if (window.analyticsManager) {
        console.log('Analytics manager ready');
    }

    console.log('Flood Prediction World Model initialized successfully');
});

// WebSocket Connection
class WebSocketManager {
    constructor() {
        this.connection = null;
        this.reconnectDelay = 5000;
        this.init();
    }

    init() {
        this.connect();
    }

    connect() {
        const wsUrl = API_CONFIG.WS_URL;
        this.connection = new WebSocket(wsUrl);

        this.connection.onopen = () => {
            console.log('WebSocket connection established');
            this.showConnectionStatus('connected');
        };

        this.connection.onmessage = (event) => {
            this.handleMessage(JSON.parse(event.data));
        };

        this.connection.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.connection.onclose = () => {
            console.log('WebSocket connection closed');
            this.showConnectionStatus('disconnected');
            this.reconnect();
        };
    }

    reconnect() {
        setTimeout(() => {
            console.log('Attempting to reconnect WebSocket...');
            this.connect();
        }, this.reconnectDelay);
    }

    handleMessage(message) {
        // Handle incoming WebSocket messages
        switch (message.type) {
            case 'simulation_update':
                Simulation.updateFromMessage(message);
                break;
            case 'visualization_update':
                Visualization.updateFromMessage(message);
                break;
            case 'alert':
                Dashboard.showNotification(message.data.message, 'warning');
                break;
            default:
                console.log('Received message:', message);
        }
    }

    showConnectionStatus(status) {
        const statusElement = document.getElementById('system-status');
        if (statusElement) {
            const statusDot = statusElement.querySelector('.status-dot');
            statusDot.className = `status-dot ${status}`;
            statusElement.querySelector('.status-text').textContent =
                status === 'connected' ? 'System Operational' : 'System Offline';
        }
    }
}

// Initialize WebSocket
new WebSocketManager();
