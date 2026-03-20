/**
 * TileStreamingController for Large Terrain
 *
 * Manages loading and displaying large terrain datasets by:
 * 1. Streaming tiles based on camera position
 * 2. Implementing LOD (Level of Detail) switching
 * 3. Caching tiles for performance
 * 4. Unloading distant tiles to save memory
 */

import * as THREE from 'three';
import { type TileData } from '../types/index';

/**
 * Configuration for tile streaming
 */
export interface TileStreamingConfig {
    tileSize?: number;
    viewDistance?: number;
    maxCacheSize?: number;
}

/**
 * TileStreamingController - Class for managing tile-based terrain rendering
 */
export class TileStreamingController {
    private scene: THREE.Scene;
    private apiBaseUrl: string;

    // Tile management
    private loadedTiles: Map<string, THREE.Mesh>;
    private tileCache: Map<string, THREE.Mesh>;
    private maxCacheSize: number;

    // Streaming configuration
    private tileSize: number;
    private viewDistance: number;
    private lodDistanceThresholds: {
        0: number;
        1: number;
        2: number;
        3: number;
    };

    // Camera tracking
    private lastCameraPosition: THREE.Vector3;
    private updateInterval: NodeJS.Timeout | null;

    // Loading queue
    private loadingQueue: string[];
    private isProcessingQueue: boolean;

    /**
     * Create a new tile streaming controller
     * @param scene - The Three.js scene
     * @param config - Streaming configuration options
     */
    constructor(scene: THREE.Scene, config: TileStreamingConfig = {}) {
        this.scene = scene;
        this.apiBaseUrl = '/api';

        // Tile management
        this.loadedTiles = new Map();
        this.tileCache = new Map();
        this.maxCacheSize = config.maxCacheSize || 20;

        // Streaming configuration
        this.tileSize = config.tileSize || 200;
        this.viewDistance = config.viewDistance || 2000;
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
     * @param fileId - DTM file ID
     */
    async initialize(fileId: string): Promise<{ tile_count: number; tiles: unknown[] }> {
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

    private dtmFileId?: string;
    private tileInfo?: unknown[];
    private totalTiles: number;

    /**
     * Start periodic tile streaming updates
     */
    startStreaming(): void {
        // Update tiles every 500ms based on camera position
        this.updateInterval = setInterval(() => {
            this.updateVisibleTiles();
        }, 500);

        console.log('Tile streaming started');
    }

    /**
     * Stop tile streaming
     */
    stopStreaming(): void {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        console.log('Tile streaming stopped');
    }

    /**
     * Update visible tiles based on camera position
     */
    async updateVisibleTiles(): Promise<void> {
        const camera = this.scene.children.find(
            (child): child is THREE.Camera => child instanceof THREE.Camera
        );

        if (!camera) return;

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
    async processLoadingQueue(): Promise<void> {
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
     * @param tileId - Tile ID to load
     */
    async loadTile(tileId: string): Promise<void> {
        // Check cache first
        if (this.tileCache.has(tileId)) {
            const mesh = this.tileCache.get(tileId);
            this.scene.add(mesh);
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
                this.scene.add(mesh);
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
     * @param tileData - Tile data from server
     */
    private createTileMesh(tileData: TileData): THREE.Mesh | null {
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
     * @param tileId - Tile ID to unload
     */
    unloadTile(tileId: string): void {
        const mesh = this.loadedTiles.get(tileId);
        if (mesh) {
            this.scene.remove(mesh);
            mesh.geometry.dispose();
            mesh.material.dispose();
            this.loadedTiles.delete(tileId);
            console.log('Unloaded tile:', tileId);
        }
    }

    /**
     * Add tile to cache
     * @param tileId - Tile ID to add to cache
     * @param mesh - Mesh to cache
     */
    private addToCache(tileId: string, mesh: THREE.Mesh): void {
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
     * @param tileId - Tile ID to update order
     */
    private updateCacheOrder(tileId: string): void {
        if (this.tileCache.has(tileId)) {
            const mesh = this.tileCache.get(tileId);
            this.tileCache.delete(tileId);
            this.tileCache.set(tileId, mesh);
        }
    }

    /**
     * Update tile stats in UI
     * @param visibleCount - Number of visible tiles
     */
    private updateTileStats(visibleCount: number): void {
        const statsEl = document.getElementById('tile-stats');
        if (statsEl) {
            statsEl.textContent = `Tiles: ${visibleCount}/${this.totalTiles || '?'}`;
        }
    }

    /**
     * Cleanup all tiles
     */
    dispose(): void {
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