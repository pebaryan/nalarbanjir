/**
 * Tile Streaming Controller for Large Terrain
 * 
 * Manages loading and displaying large terrain datasets by:
 * 1. Streaming tiles based on camera position
 * 2. Implementing LOD (Level of Detail) switching
 * 3. Caching tiles for performance
 * 4. Unloading distant tiles to save memory
 */

class TileStreamingController {
    constructor(scene3d) {
        this.scene = scene3d;
        this.apiBaseUrl = '/api';
        
        // Tile management
        this.loadedTiles = new Map(); // tile_id -> mesh
        this.tileCache = new Map(); // LRU cache
        this.maxCacheSize = 20;
        
        // Streaming configuration
        this.tileSize = 200; // pixels per tile
        this.viewDistance = 2000; // meters
        this.lodDistanceThresholds = {
            0: 500,    // Full detail within 500m
            1: 1500,   // Medium detail 500-1500m
            2: 4000,   // Low detail 1500-4000m
            3: 10000   // Very low detail beyond 4000m
        };
        
        // Camera tracking
        this.lastCameraPosition = new THREE.Vector3();
        this.updateInterval = null;
        
        // Loading queue
        this.loadingQueue = [];
        this.isProcessingQueue = false;
    }
    
    /**
     * Initialize tile streaming for a DTM
     * @param {string} fileId - DTM file ID
     */
    async initialize(fileId) {
        console.log('Initializing tile streaming for:', fileId);
        
        try {
            // Create tiles on server
            const response = await fetch(`${this.apiBaseUrl}/gis/tile-dtm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_id: fileId, max_tile_size: this.tileSize })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to create tiles: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Tiles created:', result.tile_count, 'tiles');
            
            // Store tile info
            this.dtmFileId = fileId;
            this.tileInfo = result.tiles;
            this.totalTiles = result.tile_count;
            
            // Start streaming updates
            this.startStreaming();
            
            return result;
            
        } catch (error) {
            console.error('Tile streaming initialization failed:', error);
            throw error;
        }
    }
    
    /**
     * Start periodic tile streaming updates
     */
    startStreaming() {
        // Update tiles every 500ms based on camera position
        this.updateInterval = setInterval(() => {
            this.updateVisibleTiles();
        }, 500);
        
        console.log('Tile streaming started');
    }
    
    /**
     * Stop tile streaming
     */
    stopStreaming() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        console.log('Tile streaming stopped');
    }
    
    /**
     * Update visible tiles based on camera position
     */
    async updateVisibleTiles() {
        const camera = this.scene.camera;
        const cameraPos = camera.position;
        
        // Check if camera moved significantly
        const dist = cameraPos.distanceTo(this.lastCameraPosition);
        if (dist < 50 && this.loadedTiles.size > 0) {
            return; // Camera hasn't moved much, skip update
        }
        
        this.lastCameraPosition.copy(cameraPos);
        
        try {
            // Get visible tiles from server
            const response = await fetch(`${this.apiBaseUrl}/gis/visible-tiles`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    camera_position: [cameraPos.x, cameraPos.y, cameraPos.z],
                    view_distance: this.viewDistance
                })
            });
            
            if (!response.ok) return;
            
            const result = await response.json();
            const visibleTileIds = result.visible_tiles || [];
            
            // Unload tiles that are no longer visible
            for (const [tileId, mesh] of this.loadedTiles) {
                if (!visibleTileIds.includes(tileId)) {
                    this.unloadTile(tileId);
                }
            }
            
            // Load new visible tiles
            for (const tileId of visibleTileIds) {
                if (!this.loadedTiles.has(tileId)) {
                    this.loadingQueue.push(tileId);
                }
            }
            
            // Process loading queue
            if (!this.isProcessingQueue) {
                this.processLoadingQueue();
            }
            
            // Update UI
            this.updateTileStats(visibleTileIds.length);
            
        } catch (error) {
            console.error('Error updating visible tiles:', error);
        }
    }
    
    /**
     * Process tile loading queue
     */
    async processLoadingQueue() {
        if (this.loadingQueue.length === 0) {
            this.isProcessingQueue = false;
            return;
        }
        
        this.isProcessingQueue = true;
        
        // Load next tile
        const tileId = this.loadingQueue.shift();
        await this.loadTile(tileId);
        
        // Continue processing
        setTimeout(() => this.processLoadingQueue(), 10);
    }
    
    /**
     * Load a specific tile
     * @param {string} tileId - Tile ID to load
     */
    async loadTile(tileId) {
        // Check cache first
        if (this.tileCache.has(tileId)) {
            const mesh = this.tileCache.get(tileId);
            this.scene.scene.add(mesh);
            this.loadedTiles.set(tileId, mesh);
            this.updateCacheOrder(tileId);
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/gis/tile/${tileId}`);
            if (!response.ok) return;
            
            const tileData = await response.json();
            
            // Create mesh from tile data
            const mesh = this.createTileMesh(tileData);
            
            if (mesh) {
                this.scene.scene.add(mesh);
                this.loadedTiles.set(tileId, mesh);
                this.addToCache(tileId, mesh);
                console.log('Loaded tile:', tileId);
            }
            
        } catch (error) {
            console.error('Error loading tile:', tileId, error);
        }
    }
    
    /**
     * Create Three.js mesh from tile data
     */
    createTileMesh(tileData) {
        const geometry = new THREE.BufferGeometry();
        
        // Set vertices
        const positions = new Float32Array(tileData.vertices);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        
        // Set normals if provided
        if (tileData.normals && tileData.normals.length > 0) {
            const normals = new Float32Array(tileData.normals);
            geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
        }
        
        // Set indices
        if (tileData.indices && tileData.indices.length > 0) {
            geometry.setIndex(tileData.indices);
        }
        
        geometry.computeBoundingSphere();
        
        // Create material (different color for different LOD)
        const lod = tileData.lod_level || 0;
        const colors = [0x8B7355, 0x9B8375, 0xAB9385, 0xBBA395]; // Brown shades
        
        const material = new THREE.MeshStandardMaterial({
            color: colors[Math.min(lod, 3)],
            roughness: 0.8,
            metalness: 0.1,
            flatShading: lod > 1  // Flat shading for distant tiles
        });
        
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        
        return mesh;
    }
    
    /**
     * Unload a tile from the scene
     */
    unloadTile(tileId) {
        const mesh = this.loadedTiles.get(tileId);
        if (mesh) {
            this.scene.scene.remove(mesh);
            mesh.geometry.dispose();
            mesh.material.dispose();
            this.loadedTiles.delete(tileId);
            console.log('Unloaded tile:', tileId);
        }
    }
    
    /**
     * Add tile to cache
     */
    addToCache(tileId, mesh) {
        // Remove oldest if cache is full
        if (this.tileCache.size >= this.maxCacheSize) {
            const oldestKey = this.tileCache.keys().next().value;
            const oldestMesh = this.tileCache.get(oldestKey);
            if (oldestMesh && !this.loadedTiles.has(oldestKey)) {
                oldestMesh.geometry.dispose();
                oldestMesh.material.dispose();
            }
            this.tileCache.delete(oldestKey);
        }
        
        this.tileCache.set(tileId, mesh);
    }
    
    /**
     * Update cache order (mark as recently used)
     */
    updateCacheOrder(tileId) {
        if (this.tileCache.has(tileId)) {
            const mesh = this.tileCache.get(tileId);
            this.tileCache.delete(tileId);
            this.tileCache.set(tileId, mesh);
        }
    }
    
    /**
     * Update tile stats in UI
     */
    updateTileStats(visibleCount) {
        const statsEl = document.getElementById('tile-stats');
        if (statsEl) {
            statsEl.textContent = `Tiles: ${visibleCount}/${this.totalTiles || '?'}`;
        }
    }
    
    /**
     * Cleanup all tiles
     */
    dispose() {
        this.stopStreaming();
        
        // Unload all tiles
        for (const tileId of this.loadedTiles.keys()) {
            this.unloadTile(tileId);
        }
        
        // Clear cache
        for (const mesh of this.tileCache.values()) {
            mesh.geometry.dispose();
            mesh.material.dispose();
        }
        this.tileCache.clear();
        
        console.log('Tile streaming controller disposed');
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TileStreamingController;
}
