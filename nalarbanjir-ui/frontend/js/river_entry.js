/**
 * River Geometry Entry JavaScript
 * Handles creation, listing, and management of river entries
 */

// River API endpoints
const RIVER_API = {
    create: '/api/rivers',
    list: '/api/rivers',
    get: (id) => `/api/rivers/${id}`,
    export: (id) => `/api/rivers/${id}/export`,
    mesh: (id) => `/api/rivers/${id}/mesh`,
    delete: (id) => `/api/rivers/${id}`
};

// DOM Elements
const riverForm = document.getElementById('river-form');
const riverNameInput = document.getElementById('river-name');
const riverDescriptionInput = document.getElementById('river-description');
const geometryTypeSelect = document.getElementById('geometry-type');
const geometryCoordsInput = document.getElementById('geometry-coords');
const riverWidthInput = document.getElementById('river-width');
const riverDepthInput = document.getElementById('river-depth');
const riverSlopeInput = document.getElementById('river-slope');
const riverManningInput = document.getElementById('river-manning');
const riverDischargeInput = document.getElementById('river-discharge');
const riverVelocityInput = document.getElementById('river-velocity');
const riverTimeStepInput = document.getElementById('river-time-step');
const riverTotalTimeInput = document.getElementById('river-total-time');
const riverNotesInput = document.getElementById('river-notes');
const riverListDiv = document.getElementById('river-list');

// Save River Button
document.getElementById('save-river-btn').addEventListener('click', async () => {
    await saveRiver();
});

// Clear River Button
document.getElementById('clear-river-btn').addEventListener('click', () => {
    riverForm.reset();
});

// Load Rivers
async function loadRivers() {
    try {
        const response = await fetch(RIVER_API.list);

        if (!response.ok) {
            throw new Error('Failed to load rivers');
        }

        const rivers = await response.json();

        if (rivers.rivers.length === 0) {
            riverListDiv.innerHTML = '<p>No rivers saved yet.</p>';
            return;
        }

        let html = '<div class="river-list">';
        rivers.rivers.forEach(river => {
            html += `
                <div class="river-item">
                    <div class="river-header">
                        <h4>${river.name}</h4>
                        <span class="river-type">${river.geometry.type}</span>
                    </div>
                    <p class="river-description">${river.description || 'No description'}</p>
                    <div class="river-metrics">
                        <span>Width: ${river.hydraulic_params.width}m</span>
                        <span>Depth: ${river.hydraulic_params.depth}m</span>
                        <span>Slope: ${river.hydraulic_params.slope}</span>
                    </div>
                    <div class="river-actions">
                        <button onclick="exportRiver('${river.id}')" class="btn btn-sm">Export</button>
                        <button onclick="getRiverMesh('${river.id}')" class="btn btn-sm">Get Mesh</button>
                        <button onclick="deleteRiver('${river.id}')" class="btn btn-sm btn-danger">Delete</button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        riverListDiv.innerHTML = html;
    } catch (error) {
        console.error('Error loading rivers:', error);
        riverListDiv.innerHTML = '<p style="color: #dc3545;">Error loading rivers. Please try again.</p>';
    }
}

// Save River
async function saveRiver() {
    const riverData = {
        name: riverNameInput.value,
        description: riverDescriptionInput.value,
        geometry: {
            type: geometryTypeSelect.value,
            coordinates: JSON.parse(geometryCoordsInput.value)
        },
        hydraulic_params: {
            width: parseFloat(riverWidthInput.value),
            depth: parseFloat(riverDepthInput.value),
            slope: parseFloat(riverSlopeInput.value),
            manning_n: parseFloat(riverManningInput.value),
            discharge: parseFloat(riverDischargeInput.value) || 0,
            velocity: parseFloat(riverVelocityInput.value) || 0
        },
        simulation_settings: {
            time_step: parseFloat(riverTimeStepInput.value),
            total_time: parseFloat(riverTotalTimeInput.value),
            wet_dry_threshold: 0.001
        },
        metadata: {
            tags: [],
            notes: riverNotesInput.value
        }
    };

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
            alert(`River "${riverData.name}" saved successfully!`);
            riverForm.reset();
            loadRivers();
        } else {
            alert('Error: ' + (result.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving river:', error);
        alert('Network error: ' + error.message);
    }
}

// Export River as GeoJSON
async function exportRiver(riverId) {
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

        alert(`River exported successfully!`);
    } catch (error) {
        console.error('Error exporting river:', error);
        alert('Error exporting river');
    }
}

// Get River Mesh for Solver
async function getRiverMesh(riverId) {
    try {
        const response = await fetch(RIVER_API.mesh(riverId));

        if (!response.ok) {
            throw new Error('Failed to get river mesh');
        }

        const mesh = await response.json();

        // Display mesh info
        alert(`River Mesh Generated!\n\n` +
            `River: ${mesh.river_name}\n` +
            `Bounds: (${mesh.mesh_bounds.min_x}, ${mesh.mesh_bounds.min_y}) to ` +
            `(${mesh.mesh_bounds.max_x}, ${mesh.mesh_bounds.max_y})\n` +
            `Width: ${mesh.mesh_bounds.width}m\n` +
            `Length: ${mesh.mesh_bounds.length}m\n\n` +
            `Mesh can now be used with the physics solver.`);

        console.log('Generated mesh:', mesh);
    } catch (error) {
        console.error('Error getting river mesh:', error);
        alert('Error getting river mesh');
    }
}

// Delete River
async function deleteRiver(riverId) {
    if (!confirm('Are you sure you want to delete this river?')) {
        return;
    }

    try {
        const response = await fetch(RIVER_API.delete(riverId), {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok) {
            alert(result.message);
            loadRivers();
        } else {
            alert('Error: ' + (result.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting river:', error);
        alert('Network error: ' + error.message);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadRivers();
});

// Auto-resize textarea
geometryCoordsInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});