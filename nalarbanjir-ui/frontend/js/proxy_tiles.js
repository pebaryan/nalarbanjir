/**
 * Proxy Tile System for Large DTMs
 * 
 * Provides immediate visualization by:
 * 1. Creating a very low-resolution preview mesh (whole terrain at once)
 * 2. Displaying it immediately while detailed tiles load in background
 * 3. Progressive refinement as detailed tiles become available
 */

class ProxyTileManager {
    constructor(scene3d) {
        this.scene = scene3d;
        this.proxyMesh = null;
        this.detailedTiles = new Map(); // tile_id -> mesh
        this.isLoadingDetailed = false;
        this.proxyResolution = 50; // 50x50 for preview (2500 points)
    }

    /**
     * Load a low-resolution proxy of the entire terrain immediately
     */
    async loadProxyTerrain(fileId) {
        console.log('Loading proxy terrain for immediate display...');
        
        try {
            // Request a heavily simplified mesh (1% of original resolution)
            const response = await fetch('/api/gis/generate_terrain_mesh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_id: fileId,
                    simplification: 0.01, // 1% resolution for instant load
                    z_scale: 1.0
                })
            });

            if (!response.ok) {
                throw new Error('Failed to generate proxy terrain');
            }

            const result = await response.json();
            
            // Load the proxy mesh
            const meshResponse = await fetch(`/api/gis/mesh/${result.mesh_id}`);
            const meshData = await meshResponse.json();

            // Convert and display
            const geometry = this.convertToGeometry(meshData.threejs_geometry);
            
            // Semi-transparent material to show it's a preview
            const material = new THREE.MeshStandardMaterial({
                color: 0x8B7355,
                roughness: 0.9,
                metalness: 0.1,
                transparent: true,
                opacity: 0.7
            });

            this.proxyMesh = new THREE.Mesh(geometry, material);
            this.proxyMesh.name = 'proxy_terrain';
            this.scene.scene.add(this.proxyMesh);

            console.log('✓ Proxy terrain loaded immediately');
            return result;

        } catch (error) {
            console.error('Proxy terrain load failed:', error);
            throw error;
        }
    }

    /**
     * Start loading detailed tiles in background
     */
    async startDetailedLoading(fileId, onProgress) {
        console.log('Starting detailed tile loading...');
        this.isLoadingDetailed = true;

        try {
            // Start async tiling
            const response = await fetch('/api/gis/tile-async', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_id: fileId })
            });

            const { task_id } = await response.json();
            console.log('Tiling task started:', task_id);

            // Poll for progress
            this.pollTilingProgress(task_id, onProgress);

        } catch (error) {
            console.error('Detailed loading failed:', error);
        }
    }

    /**
     * Poll for tiling progress and load tiles as they're ready
     */
    async pollTilingProgress(taskId, onProgress) {
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/gis/tiling-progress/${taskId}`);
                const progress = await response.json();

                if (onProgress) {
                    onProgress(progress);
                }

                // If completed, start streaming tiles
                if (progress.status === 'completed') {
                    clearInterval(pollInterval);
                    console.log('Tiling complete, streaming tiles...');
                    this.streamTiles(progress.tile_ids);
                }

            } catch (error) {
                console.error('Progress poll error:', error);
                clearInterval(pollInterval);
            }
        }, 1000); // Poll every second
    }

    /**
     * Stream detailed tiles and replace proxy progressively
     */
    async streamTiles(tileIds) {
        console.log(`Streaming ${tileIds.length} detailed tiles...`);

        for (let i = 0; i < tileIds.length; i++) {
            const tileId = tileIds[i];
            
            try {
                // Load tile
                const response = await fetch(`/api/gis/tile/${tileId}`);
                const tileData = await response.json();

                // Create detailed mesh
                const geometry = this.convertToGeometry(tileData);
                const material = new THREE.MeshStandardMaterial({
                    color: 0x8B7355,
                    roughness: 0.8,
                    metalness: 0.1
                });

                const detailedMesh = new THREE.Mesh(geometry, material);
                detailedMesh.name = `tile_${tileId}`;

                // Hide proxy for this area and show detailed tile
                // (In a real implementation, you'd only hide the overlapping portion)
                this.scene.scene.add(detailedMesh);
                this.detailedTiles.set(tileId, detailedMesh);

                // Update progress
                const percent = Math.round(((i + 1) / tileIds.length) * 100);
                console.log(`Loaded tile ${i + 1}/${tileIds.length} (${percent}%)`);

                // Small delay to prevent UI freezing
                await new Promise(r => setTimeout(r, 10));

            } catch (error) {
                console.error(`Failed to load tile ${tileId}:`, error);
            }
        }

        // Remove proxy mesh once all detailed tiles are loaded
        this.removeProxy();
        console.log('✓ All detailed tiles loaded, proxy removed');
    }

    /**
     * Convert server mesh data to Three.js geometry
     */
    convertToGeometry(meshData) {
        const geometry = new THREE.BufferGeometry();

        const positions = new Float32Array(meshData.data.attributes.position.array);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        if (meshData.data.index) {
            geometry.setIndex(meshData.data.index.array);
        }

        geometry.computeBoundingSphere();
        return geometry;
    }

    /**
     * Remove proxy mesh
     */
    removeProxy() {
        if (this.proxyMesh) {
            this.scene.scene.remove(this.proxyMesh);
            this.proxyMesh.geometry.dispose();
            this.proxyMesh.material.dispose();
            this.proxyMesh = null;
            console.log('Proxy terrain removed');
        }
    }

    /**
     * Get current loading status
     */
    getStatus() {
        return {
            hasProxy: this.proxyMesh !== null,
            detailedTileCount: this.detailedTiles.size,
            isLoadingDetailed: this.isLoadingDetailed
        };
    }

    /**
     * Dispose all resources
     */
    dispose() {
        this.removeProxy();
        
        for (const mesh of this.detailedTiles.values()) {
            this.scene.scene.remove(mesh);
            mesh.geometry.dispose();
            mesh.material.dispose();
        }
        this.detailedTiles.clear();
    }
}

// Usage example:
// const proxyManager = new ProxyTileManager(window.scene3D);
// await proxyManager.loadProxyTerrain(fileId); // Immediate low-res display
// proxyManager.startDetailedLoading(fileId, (progress) => {
//     console.log(`Tiling: ${progress.progress}%`);
// });
