/**
 * ProxyTileSystem for Large DTMs
 *
 * Provides immediate visualization by:
 * 1. Creating a very low-resolution preview mesh (whole terrain at once)
 * 2. Displaying it immediately while detailed tiles load in background
 * 3. Progressive refinement as detailed tiles become available
 */

import * as THREE from 'three';
import { type TileData } from '../types/index';

/**
 * ProxyTileManager - Class for managing low-resolution proxy terrain
 */
export class ProxyTileManager {
    private scene: THREE.Scene;
    private proxyMesh: THREE.Mesh | null;
    private detailedTiles: Map<string, THREE.Mesh>;
    private isLoadingDetailed: boolean;
    private proxyResolution: number;

    /**
     * Create a new proxy tile manager
     * @param scene - The Three.js scene
     */
    constructor(scene: THREE.Scene) {
        this.scene = scene;
        this.proxyMesh = null;
        this.detailedTiles = new Map();
        this.isLoadingDetailed = false;
        this.proxyResolution = 50; // 50x50 for preview (2500 points)
    }

    /**
     * Load a low-resolution proxy of the entire terrain immediately
     * @param fileId - DTM file ID
     * @returns {Promise} - Mesh generation result
     */
    async loadProxyTerrain(fileId: string): Promise<{ mesh_id: string }> {
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
            this.scene.add(this.proxyMesh);

            console.log('✓ Proxy terrain loaded immediately');
            return result;

        } catch (error) {
            console.error('Proxy terrain load failed:', error);
            throw error;
        }
    }

    /**
     * Start loading detailed tiles in background
     * @param fileId - DTM file ID
     * @param onProgress - Progress callback
     */
    async startDetailedLoading(fileId: string, onProgress?: (progress: any) => void): Promise<{ task_id: string }> {
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

            return { task_id };

        } catch (error) {
            console.error('Detailed loading failed:', error);
            throw error;
        }
    }

    /**
     * Poll for tiling progress and load tiles as they're ready
     * @param taskId - Tiling task ID
     * @param onProgress - Progress callback
     */
    async pollTilingProgress(taskId: string, onProgress?: (progress: any) => void): Promise<void> {
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
     * @param tileIds - Array of tile IDs to stream
     */
    async streamTiles(tileIds: string[]): Promise<void> {
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
                this.scene.add(detailedMesh);
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
     * @param meshData - Three.js geometry data from server
     */
    private convertToGeometry(meshData: { data: { attributes: { position?: { array: number[] }; index?: { array: number[] } } } }): THREE.BufferGeometry {
        const geometry = new THREE.BufferGeometry();

        const positions = new Float32Array(meshData.data.attributes.position?.array || []);
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
    removeProxy(): void {
        if (this.proxyMesh) {
            this.scene.remove(this.proxyMesh);
            this.proxyMesh.geometry.dispose();
            this.proxyMesh.material.dispose();
            this.proxyMesh = null;
            console.log('Proxy terrain removed');
        }
    }

    /**
     * Get current loading status
     * @returns Object with current status
     */
    getStatus(): {
        hasProxy: boolean;
        detailedTileCount: number;
        isLoadingDetailed: boolean;
    } {
        return {
            hasProxy: this.proxyMesh !== null,
            detailedTileCount: this.detailedTiles.size,
            isLoadingDetailed: this.isLoadingDetailed
        };
    }

    /**
     * Dispose of all resources
     */
    dispose(): void {
        this.removeProxy();

        for (const mesh of this.detailedTiles.values()) {
            this.scene.remove(mesh);
            mesh.geometry.dispose();
            mesh.material.dispose();
        }
        this.detailedTiles.clear();
    }
}