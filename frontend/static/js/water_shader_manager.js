/**
 * WaterShaderManager - Manages water surface rendering with custom shaders
 * 
 * This class integrates the water shaders with Three.js materials and provides
 * an easy-to-use interface for creating and updating water surfaces with
 * realistic rendering effects.
 */

class WaterShaderManager {
    /**
     * Create a new water shader manager
     * @param {THREE.Scene} scene - The Three.js scene
     * @param {THREE.Camera} camera - The camera for view-dependent effects
     * @param {Object} options - Configuration options
     */
    constructor(scene, camera, options = {}) {
        this.scene = scene;
        this.camera = camera;
        
        // Default options
        this.options = {
            preset: options.preset || 'calm',
            enableReflection: options.enableReflection !== undefined ? options.enableReflection : false,
            enableRefraction: options.enableRefraction !== undefined ? options.enableRefraction : false,
            enableNormalMap: options.enableNormalMap !== undefined ? options.enableNormalMap : false,
            ...options
        };
        
        // Get preset configuration
        this.preset = WATER_PRESETS[this.options.preset] || WATER_PRESETS.calm;
        
        // Uniforms for the shader
        this.uniforms = {
            uTime: { value: 0 },
            uWaveHeight: { value: this.preset.waveHeight },
            uWaveSpeed: { value: this.preset.waveSpeed },
            uWaveFrequency: { value: this.preset.waveFrequency },
            uCameraPosition: { value: new THREE.Vector3() },
            uShallowColor: { value: this.preset.shallowColor },
            uDeepColor: { value: this.preset.deepColor },
            uFoamColor: { value: this.preset.foamColor },
            uColorDepthScale: { value: this.preset.colorDepthScale },
            uFoamThreshold: { value: this.preset.foamThreshold },
            uLightDirection: { value: new THREE.Vector3(0.5, 1.0, 0.5).normalize() },
            uLightColor: { value: new THREE.Color(1.0, 1.0, 0.9) },
            uLightIntensity: { value: 1.0 },
            uAmbientLight: { value: 0.3 },
            uReflectivity: { value: this.preset.reflectivity },
            uFresnelPower: { value: this.preset.fresnelPower },
            uRefractionStrength: { value: 0.02 },
            uShininess: { value: this.preset.shininess },
            uSpecularity: { value: this.preset.specularity },
            uNormalScale: { value: this.preset.normalScale },
            uNormalSpeed: { value: this.preset.normalSpeed },
        };
        
        // Reflection/Refraction textures (if enabled)
        if (this.options.enableReflection) {
            this.uniforms.uReflectionTexture = { value: null };
        }
        if (this.options.enableRefraction) {
            this.uniforms.uRefractionTexture = { value: null };
        }
        if (this.options.enableNormalMap) {
            this.uniforms.uNormalMap = { value: this.createNormalMap() };
        }
        
        // Create the shader material
        this.material = this.createMaterial();
        
        // Store water meshes
        this.waterMeshes = new Map();
        
        // Animation state
        this.isAnimating = false;
        this.clock = new THREE.Clock();
    }
    
    /**
     * Create the shader material
     * @returns {THREE.ShaderMaterial} The configured shader material
     */
    createMaterial() {
        // Build defines based on enabled features
        const defines = {};
        if (this.options.enableReflection) {
            defines.USE_REFLECTION = '';
        }
        if (this.options.enableRefraction) {
            defines.USE_REFRACTION = '';
        }
        if (this.options.enableNormalMap) {
            defines.USE_NORMAL_MAP = '';
        }
        
        return new THREE.ShaderMaterial({
            vertexShader: WATER_VERTEX_SHADER,
            fragmentShader: WATER_FRAGMENT_SHADER,
            uniforms: this.uniforms,
            defines: defines,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false,  // Prevent z-fighting with terrain
            depthTest: true,
        });
    }
    
    /**
     * Create a procedural normal map for water surface detail
     * @returns {THREE.Texture} The generated normal map
     */
    createNormalMap() {
        const size = 512;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        
        // Create noise pattern
        const imageData = ctx.createImageData(size, size);
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const i = (y * size + x) * 4;
                
                // Generate multiple octaves of noise
                let noise = 0;
                noise += Math.sin(x * 0.05) * Math.cos(y * 0.05) * 0.5;
                noise += Math.sin(x * 0.1 + y * 0.05) * 0.25;
                noise += Math.sin(x * 0.2) * Math.sin(y * 0.2) * 0.125;
                
                // Convert to normal map (simplified)
                const r = 128 + noise * 127;
                const g = 128 + noise * 127;
                const b = 255;
                
                imageData.data[i] = r;
                imageData.data[i + 1] = g;
                imageData.data[i + 2] = b;
                imageData.data[i + 3] = 255;
            }
        }
        
        ctx.putImageData(imageData, 0, 0);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        
        return texture;
    }
    
    /**
     * Create a water mesh from geometry
     * @param {string} id - Unique identifier for the water mesh
     * @param {THREE.BufferGeometry} geometry - The water surface geometry
     * @param {Object} options - Additional options for this specific mesh
     * @returns {THREE.Mesh} The created water mesh
     */
    createWaterMesh(id, geometry, options = {}) {
        // Clone material for this mesh if needed
        const material = options.useSharedMaterial ? this.material : this.material.clone();

        // Create mesh
        const mesh = new THREE.Mesh(geometry, material);
        mesh.name = `water_surface_${id}`;

        // Ensure water renders on top of terrain (higher render order for transparent objects)
        mesh.renderOrder = 1;

        // Add polygon offset to prevent z-fighting with terrain
        mesh.material.polygonOffset = true;
        mesh.material.polygonOffsetFactor = -1.0;  // Pull toward camera
        mesh.material.polygonOffsetUnits = -1.0;

        // Store reference
        this.waterMeshes.set(id, {
            mesh: mesh,
            material: material,
            options: options
        });

        // Add to scene
        this.scene.add(mesh);

        return mesh;
    }
    
    /**
     * Remove a water mesh
     * @param {string} id - The mesh ID to remove
     */
    removeWaterMesh(id) {
        const waterData = this.waterMeshes.get(id);
        if (waterData) {
            this.scene.remove(waterData.mesh);
            waterData.mesh.geometry.dispose();
            if (waterData.material !== this.material) {
                waterData.material.dispose();
            }
            this.waterMeshes.delete(id);
        }
    }
    
    /**
     * Update shader uniforms (call in animation loop)
     */
    update() {
        if (!this.isAnimating) return;
        
        // Update time
        this.uniforms.uTime.value = this.clock.getElapsedTime();
        
        // Update camera position
        if (this.camera) {
            this.uniforms.uCameraPosition.value.copy(this.camera.position);
        }
        
        // Update reflection/refraction if enabled
        if (this.options.enableReflection || this.options.enableRefraction) {
            this.updateReflectionRefraction();
        }
    }
    
    /**
     * Update reflection and refraction textures
     * @private
     */
    updateReflectionRefraction() {
        // This would require a more complex setup with a separate render target
        // For now, this is a placeholder for future implementation
        // In a full implementation, you would:
        // 1. Render scene to reflection texture (clipped by water plane)
        // 2. Render scene to refraction texture (underwater view)
        // 3. Update the uniform values
    }
    
    /**
     * Set the wave parameters
     * @param {Object} params - Wave parameters
     * @param {number} params.height - Wave height
     * @param {number} params.speed - Wave speed
     * @param {number} params.frequency - Wave frequency
     */
    setWaveParameters(params) {
        if (params.height !== undefined) {
            this.uniforms.uWaveHeight.value = params.height;
        }
        if (params.speed !== undefined) {
            this.uniforms.uWaveSpeed.value = params.speed;
        }
        if (params.frequency !== undefined) {
            this.uniforms.uWaveFrequency.value = params.frequency;
        }
    }
    
    /**
     * Set the water color
     * @param {Object} colors - Color parameters
     * @param {THREE.Color} colors.shallow - Shallow water color
     * @param {THREE.Color} colors.deep - Deep water color
     * @param {THREE.Color} colors.foam - Foam color
     */
    setWaterColor(colors) {
        if (colors.shallow) {
            this.uniforms.uShallowColor.value = colors.shallow;
        }
        if (colors.deep) {
            this.uniforms.uDeepColor.value = colors.deep;
        }
        if (colors.foam) {
            this.uniforms.uFoamColor.value = colors.foam;
        }
    }
    
    /**
     * Set lighting parameters
     * @param {Object} params - Lighting parameters
     * @param {THREE.Vector3} params.direction - Light direction
     * @param {THREE.Color} params.color - Light color
     * @param {number} params.intensity - Light intensity
     * @param {number} params.ambient - Ambient light level
     */
    setLighting(params) {
        if (params.direction) {
            this.uniforms.uLightDirection.value.copy(params.direction).normalize();
        }
        if (params.color) {
            this.uniforms.uLightColor.value = params.color;
        }
        if (params.intensity !== undefined) {
            this.uniforms.uLightIntensity.value = params.intensity;
        }
        if (params.ambient !== undefined) {
            this.uniforms.uAmbientLight.value = params.ambient;
        }
    }
    
    /**
     * Apply a preset configuration
     * @param {string} presetName - Name of the preset ('calm', 'moderate', 'rough', 'flood')
     */
    applyPreset(presetName) {
        const preset = WATER_PRESETS[presetName];
        if (!preset) {
            console.warn(`Unknown preset: ${presetName}`);
            return;
        }
        
        this.setWaveParameters({
            height: preset.waveHeight,
            speed: preset.waveSpeed,
            frequency: preset.waveFrequency
        });
        
        this.setWaterColor({
            shallow: preset.shallowColor,
            deep: preset.deepColor,
            foam: preset.foamColor
        });
        
        this.uniforms.uColorDepthScale.value = preset.colorDepthScale;
        this.uniforms.uFoamThreshold.value = preset.foamThreshold;
        this.uniforms.uReflectivity.value = preset.reflectivity;
        this.uniforms.uFresnelPower.value = preset.fresnelPower;
        this.uniforms.uShininess.value = preset.shininess;
        this.uniforms.uSpecularity.value = preset.specularity;
        this.uniforms.uNormalScale.value = preset.normalScale;
        this.uniforms.uNormalSpeed.value = preset.normalSpeed;
    }
    
    /**
     * Start the water animation
     */
    startAnimation() {
        this.isAnimating = true;
        this.clock.start();
    }
    
    /**
     * Stop the water animation
     */
    stopAnimation() {
        this.isAnimating = false;
        this.clock.stop();
    }
    
    /**
     * Get all water meshes
     * @returns {Map} Map of water mesh IDs to mesh data
     */
    getAllMeshes() {
        return this.waterMeshes;
    }
    
    /**
     * Dispose of all resources
     */
    dispose() {
        // Remove all meshes
        for (const [id, data] of this.waterMeshes) {
            this.removeWaterMesh(id);
        }
        
        // Dispose of main material
        this.material.dispose();
        
        // Clear references
        this.waterMeshes.clear();
        this.scene = null;
        this.camera = null;
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WaterShaderManager;
}
