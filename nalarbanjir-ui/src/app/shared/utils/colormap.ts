import * as THREE from 'three';

export type ColormapName = 'terrain' | 'blues' | 'risk' | 'viridis' | 'plasma' | 'reds' | 'greens';

// colour stops: [t∈[0,1], hex]
const STOPS: Record<ColormapName, [number, string][]> = {
  terrain: [
    [0.00, '#1a3a2a'],
    [0.30, '#2d6a4f'],
    [0.55, '#74c69d'],
    [0.72, '#d4a574'],
    [0.88, '#c8b89a'],
    [1.00, '#f0ece4'],
  ],
  blues: [
    [0.00, '#dbeafe'],
    [0.30, '#60a5fa'],
    [0.65, '#1d4ed8'],
    [1.00, '#1e3a8a'],
  ],
  risk: [
    [0.00, '#22c55e'],   // 0 — none
    [0.25, '#eab308'],   // 1 — minor
    [0.50, '#f97316'],   // 2 — moderate
    [0.75, '#ef4444'],   // 3 — major
    [1.00, '#7f1d1d'],   // 4 — severe
  ],
  viridis: [
    [0.00, '#440154'],
    [0.25, '#31688e'],
    [0.50, '#35b779'],
    [0.75, '#90d743'],
    [1.00, '#fde725'],
  ],
  plasma: [
    [0.00, '#0d0887'],
    [0.25, '#7e03a8'],
    [0.50, '#cc4778'],
    [0.75, '#f89441'],
    [1.00, '#f0f921'],
  ],
  reds: [
    [0.00, '#fff5f0'],
    [0.50, '#fc8d59'],
    [1.00, '#67000d'],
  ],
  greens: [
    [0.00, '#f7fcf5'],
    [0.50, '#74c476'],
    [1.00, '#00441b'],
  ],
};

const _cache = new Map<string, THREE.Color>();

export function sampleColormap(t: number, name: ColormapName): THREE.Color {
  const key = `${name}:${Math.round(t * 1000)}`;
  const cached = _cache.get(key);
  if (cached) return cached;

  const stops = STOPS[name] ?? STOPS.terrain;
  const tc = Math.max(0, Math.min(1, t));

  let col: THREE.Color;
  if (tc <= stops[0][0]) {
    col = new THREE.Color(stops[0][1]);
  } else if (tc >= stops[stops.length - 1][0]) {
    col = new THREE.Color(stops[stops.length - 1][1]);
  } else {
    col = new THREE.Color();
    for (let i = 1; i < stops.length; i++) {
      const [t0, c0] = stops[i - 1];
      const [t1, c1] = stops[i];
      if (tc <= t1) {
        const alpha = (tc - t0) / (t1 - t0);
        col.set(c0).lerp(new THREE.Color(c1), alpha);
        break;
      }
    }
  }

  if (_cache.size > 4000) _cache.clear();
  _cache.set(key, col);
  return col;
}

export const COLORMAPS: ColormapName[] = ['terrain', 'blues', 'viridis', 'plasma', 'reds', 'greens', 'risk'];
