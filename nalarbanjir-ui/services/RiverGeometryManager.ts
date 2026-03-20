/**
 * River Geometry Manager
 *
 * Handles creation, listing, and management of river entries
 */

import * as THREE from 'three';
import { type RiverGeometry, type HydraulicParams } from '../types/index';

/**
 * River API endpoints
 */
const RIVER_API = {
    create: '/api/rivers',
    list: '/api/rivers',
    get: (id: string) => `/api/rivers/${id}`,
    export: (id: string) => `/api/rivers/${id}/export`,
    mesh: (id: string) => `/api/rivers/${id}/mesh`,
    delete: (id: string) => `/api/rivers/${id}`
};

/**
 * River geometry data
 */
interface RiverData {
    id: string;
    name: string;
    description: string;
    geometry: RiverGeometry;
    hydraulic_params: HydraulicParams;
    simulation_settings: {
        time_step: number;
        total_time: number;
        wet_dry_threshold: number;
    };
    metadata: {
        tags: string[];
        notes: string;
    };
}

/**
 * River mesh data
 */
interface RiverMeshData {
    river_name: string;
    mesh_bounds: {
        min_x: number;
        min_y: number;
        max_x: number;
        max_y: number;
        width: number;
        length: number;
    };
}

/**
 * RiverGeometryManager - Class for managing river geometry
 */
export class RiverGeometryManager {
    /**
     * Save a new river
     * @param riverData - River data to save
     * @returns {Promise} - Server response
     */
    async saveRiver(riverData: RiverData): Promise<{ river_id: string }> {
        try {
            const response = await fetch(RIVER_API.create, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(riverData)
            });

            const result = await response.json();

            if (response.ok) {
                console.log(`River "${riverData.name}" saved successfully!`);
                return result;
            } else {
                throw new Error(result.detail || 'Unknown error');
            }
        } catch (error) {
            console.error('Error saving river:', error);
            throw error;
        }
    }

    /**
     * Load all rivers
     * @returns {Promise<Array>} - Array of rivers
     */
    async loadRivers(): Promise<RiverData[]> {
        try {
            const response = await fetch(RIVER_API.list);

            if (!response.ok) {
                throw new Error('Failed to load rivers');
            }

            const data = await response.json();
            return data.rivers || [];

        } catch (error) {
            console.error('Error loading rivers:', error);
            throw error;
        }
    }

    /**
     * Export a river as GeoJSON
     * @param riverId - River ID to export
     * @returns {Promise} - Export data
     */
    async exportRiver(riverId: string): Promise<{ river_id: string; data: any }> {
        try {
            const response = await fetch(RIVER_API.export(riverId));

            if (!response.ok) {
                throw new Error('Failed to export river');
            }

            const result = await response.json();

            // Download as JSON file
            const dataStr = JSON.stringify(result.data, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);

            const link = document.createElement('a');
            link.href = url;
            link.download = `${result.river_id}.geojson`;
            link.click();

            URL.revokeObjectURL(url);

            console.log(`River exported successfully!`);
            return result;

        } catch (error) {
            console.error('Error exporting river:', error);
            throw error;
        }
    }

    /**
     * Get river mesh for solver
     * @param riverId - River ID
     * @returns {Promise} - Mesh data
     */
    async getRiverMesh(riverId: string): Promise<RiverMeshData> {
        try {
            const response = await fetch(RIVER_API.mesh(riverId));

            if (!response.ok) {
                throw new Error('Failed to get river mesh');
            }

            const mesh = await response.json();

            console.log(`River Mesh Generated!\n\n` +
                `River: ${mesh.river_name}\n` +
                `Bounds: (${mesh.mesh_bounds.min_x}, ${mesh.mesh_bounds.min_y}) to ` +
                `(${mesh.mesh_bounds.max_x}, ${mesh.mesh_bounds.max_y})\n` +
                `Width: ${mesh.mesh_bounds.width}m\n` +
                `Length: ${mesh.mesh_bounds.length}m\n\n` +
                `Mesh can now be used with the physics solver.`);

            return mesh;

        } catch (error) {
            console.error('Error getting river mesh:', error);
            throw error;
        }
    }

    /**
     * Delete a river
     * @param riverId - River ID to delete
     * @returns {Promise} - Server response
     */
    async deleteRiver(riverId: string): Promise<{ message: string }> {
        try {
            const response = await fetch(RIVER_API.delete(riverId), {
                method: 'DELETE'
            });

            const result = await response.json();

            if (response.ok) {
                console.log(`River deleted: ${riverId}`);
                return result;
            } else {
                throw new Error(result.detail || 'Unknown error');
            }
        } catch (error) {
            console.error('Error deleting river:', error);
            throw error;
        }
    }
}