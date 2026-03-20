/**
 * Water Surface Shaders for Flood Prediction World Model
 *
 * Provides realistic water rendering with:
 * - Vertex animation for waves
 * - Reflection and refraction
 * - Fresnel effects
 * - Depth-based coloring
 * - Normal mapping for surface detail
 */

// ============================================================================
// VERTEX SHADER
// ============================================================================
export const WATER_VERTEX_SHADER = `
    // Standard Three.js uniforms (automatically provided)
    // Don't declare position, normal, uv as attributes - Three.js handles them

    // Wave uniforms
    uniform float uTime;
    uniform float uWaveHeight;
    uniform float uWaveSpeed;
    uniform float uWaveFrequency;

    // Varying outputs to fragment shader
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vWorldPosition;
    varying float vElevation;

    // Wave functions
    float sineWave(vec2 pos, float frequency, float speed, float time) {
        return sin(pos.x * frequency + time * speed) *
               cos(pos.y * frequency * 0.5 + time * speed * 0.8);
    }

    void main() {
        vUv = uv;

        // Calculate wave displacement
        vec3 displacedPosition = position;

        // Primary wave
        float wave1 = sineWave(position.xy, uWaveFrequency, uWaveSpeed, uTime);

        // Secondary wave (smaller, faster)
        float wave2 = sineWave(position.xy, uWaveFrequency * 2.0, uWaveSpeed * 1.5, uTime) * 0.5;

        // Tertiary wave (detail)
        float wave3 = sineWave(position.xy, uWaveFrequency * 4.0, uWaveSpeed * 2.0, uTime) * 0.25;

        // Combine waves
        float totalWave = wave1 + wave2 + wave3;
        displacedPosition.z += totalWave * uWaveHeight;

        // Approximate normal from wave derivatives
        float dx = cos(position.x * uWaveFrequency + uTime * uWaveSpeed) * uWaveFrequency * uWaveHeight;
        float dy = cos(position.y * uWaveFrequency * 0.5 + uTime * uWaveSpeed * 0.8) * uWaveFrequency * 0.5 * uWaveHeight;

        vec3 waveNormal = normalize(vec3(-dx, -dy, 1.0));
        vNormal = normalize(normalMatrix * waveNormal);

        // Calculate world position
        vec4 worldPosition = modelMatrix * vec4(displacedPosition, 1.0);
        vWorldPosition = worldPosition.xyz;
        vPosition = displacedPosition;
        vElevation = displacedPosition.z;

        // Final position
        gl_Position = projectionMatrix * viewMatrix * worldPosition;
    }
`;

// ============================================================================
// FRAGMENT SHADER - Simplified for uniform water color
// ============================================================================
export const WATER_FRAGMENT_SHADER = `
    precision highp float;

    // Varying inputs from vertex shader
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vWorldPosition;
    varying float vElevation;

    // Uniforms
    uniform float uTime;
    uniform vec3 uCameraPosition;

    // Water color uniforms
    uniform vec3 uShallowColor;
    uniform vec3 uDeepColor;
    uniform vec3 uFoamColor;
    uniform float uColorDepthScale;
    uniform float uFoamThreshold;

    // Lighting uniforms
    uniform vec3 uLightDirection;
    uniform vec3 uLightColor;
    uniform float uLightIntensity;
    uniform float uAmbientLight;

    // Utils
    const float PI = 3.14159265359;

    void main() {
        // Light direction
        vec3 lightDir = normalize(uLightDirection);

        // Simple diffuse lighting only (no view-dependent effects)
        float diff = max(dot(vNormal, lightDir), 0.0);

        // Base water color with simple lighting
        vec3 waterColor = uShallowColor;
        vec3 finalColor = waterColor * (diff * uLightIntensity + uAmbientLight);

        // Uniform transparency - no fresnel-based alpha changes
        gl_FragColor = vec4(finalColor, 0.75);
    }
`;

// ============================================================================
// SHADER CONFIGURATION PRESETS
// ============================================================================

export interface WaterPreset {
    waveHeight: number;
    waveSpeed: number;
    waveFrequency: number;
    shallowColor: THREE.Color;
    deepColor: THREE.Color;
    foamColor: THREE.Color;
    colorDepthScale: number;
    foamThreshold: number;
    reflectivity: number;
    fresnelPower: number;
    shininess: number;
    specularity: number;
    normalScale: number;
    normalSpeed: number;
}

export const WATER_PRESETS: Record<string, WaterPreset> = {
    calm: {
        waveHeight: 0.3,
        waveSpeed: 0.5,
        waveFrequency: 0.2,
        shallowColor: new THREE.Color(0x4a90e2),
        deepColor: new THREE.Color(0x1a5490),
        foamColor: new THREE.Color(0xffffff),
        colorDepthScale: 1.0,
        foamThreshold: 0.25,
        reflectivity: 0.3,
        fresnelPower: 2.0,
        shininess: 0.3,
        specularity: 0.5,
        normalScale: 0.3,
        normalSpeed: 0.5,
    },

    moderate: {
        waveHeight: 0.8,
        waveSpeed: 1.0,
        waveFrequency: 0.3,
        shallowColor: new THREE.Color(0x5ba3f5),
        deepColor: new THREE.Color(0x2a6ab5),
        foamColor: new THREE.Color(0xffffff),
        colorDepthScale: 1.2,
        foamThreshold: 0.4,
        reflectivity: 0.4,
        fresnelPower: 2.5,
        shininess: 0.4,
        specularity: 0.7,
        normalScale: 0.5,
        normalSpeed: 1.0,
    },

    rough: {
        waveHeight: 2.0,
        waveSpeed: 2.0,
        waveFrequency: 0.5,
        shallowColor: new THREE.Color(0x6bb6ff),
        deepColor: new THREE.Color(0x3a7bc8),
        foamColor: new THREE.Color(0xffffff),
        colorDepthScale: 1.5,
        foamThreshold: 0.6,
        reflectivity: 0.5,
        fresnelPower: 3.0,
        shininess: 0.5,
        specularity: 1.0,
        normalScale: 0.7,
        normalSpeed: 1.5,
    },

    flood: {
        waveHeight: 1.5,
        waveSpeed: 1.5,
        waveFrequency: 0.4,
        shallowColor: new THREE.Color(0x8B4513), // Brownish for muddy flood water
        deepColor: new THREE.Color(0x4a3728),
        foamColor: new THREE.Color(0xdcdcdc),
        colorDepthScale: 2.0,
        foamThreshold: 0.5,
        reflectivity: 0.2,
        fresnelPower: 1.5,
        shininess: 0.2,
        specularity: 0.3,
        normalScale: 0.4,
        normalSpeed: 1.2,
    }
};

// ============================================================================
// EXPORTS
// ============================================================================

export {
    WATER_VERTEX_SHADER,
    WATER_FRAGMENT_SHADER
};