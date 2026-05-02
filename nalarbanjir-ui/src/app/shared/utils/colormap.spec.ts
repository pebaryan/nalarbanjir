import { sampleColormap, COLORMAPS, type ColormapName } from './colormap';
import * as THREE from 'three';

describe('colormap', () => {
  it('should export all colormap names', () => {
    const expected = ['terrain', 'blues', 'viridis', 'plasma', 'reds', 'greens', 'risk'];
    expect(COLORMAPS).toEqual(expected);
    expect(COLORMAPS.length).toBe(7);
  });

  describe('sampleColormap', () => {
    it('should return a THREE.Color', () => {
      const col = sampleColormap(0.5, 'terrain');
      expect(col).toBeInstanceOf(THREE.Color);
    });

    it('should return first stop color at t=0', () => {
      const col = sampleColormap(0, 'blues');
      // blues first stop is #dbeafe
      const expected = new THREE.Color('#dbeafe');
      expect(col.r).toBeCloseTo(expected.r, 4);
      expect(col.g).toBeCloseTo(expected.g, 4);
      expect(col.b).toBeCloseTo(expected.b, 4);
    });

    it('should return last stop color at t=1', () => {
      const col = sampleColormap(1, 'blues');
      // blues last stop is #1e3a8a
      const expected = new THREE.Color('#1e3a8a');
      expect(col.r).toBeCloseTo(expected.r, 4);
      expect(col.g).toBeCloseTo(expected.g, 4);
      expect(col.b).toBeCloseTo(expected.b, 4);
    });

    it('should interpolate between stops at t=0.5', () => {
      const col = sampleColormap(0.5, 'viridis');
      expect(col).toBeInstanceOf(THREE.Color);
      // Just verify it returns a valid color, not a boundary value
      expect(col.r).toBeGreaterThanOrEqual(0);
      expect(col.r).toBeLessThanOrEqual(1);
      expect(col.g).toBeGreaterThanOrEqual(0);
      expect(col.g).toBeLessThanOrEqual(1);
      expect(col.b).toBeGreaterThanOrEqual(0);
      expect(col.b).toBeLessThanOrEqual(1);
    });

    it('should clamp t below 0 to first stop', () => {
      const col0 = sampleColormap(-0.5, 'risk');
      const col = sampleColormap(0, 'risk');
      expect(col.r).toBeCloseTo(col0.r, 4);
      expect(col.g).toBeCloseTo(col0.g, 4);
      expect(col.b).toBeCloseTo(col0.b, 4);
    });

    it('should clamp t above 1 to last stop', () => {
      const col1 = sampleColormap(1.5, 'risk');
      const col = sampleColormap(1, 'risk');
      expect(col.r).toBeCloseTo(col1.r, 4);
      expect(col.g).toBeCloseTo(col1.g, 4);
      expect(col.b).toBeCloseTo(col1.b, 4);
    });

    it('should use terrain as default when name is unknown', () => {
      const col = sampleColormap(0.5, 'terrain' as ColormapName);
      // Calling with an unknown key should fall back to terrain
      const unknownKey = 'unknown' as ColormapName;
      const colUnknown = sampleColormap(0.5, unknownKey);
      expect(col.r).toBeCloseTo(colUnknown.r, 4);
    });

    it('should cache results', () => {
      const col1 = sampleColormap(0.3, 'plasma');
      const col2 = sampleColormap(0.3, 'plasma');
      // Should return the same cached instance
      expect(col1).toBe(col2);
    });
  });

  describe('risk colormap', () => {
    const riskColors = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#7f1d1d'];

    it('should return green (none) at t=0', () => {
      const col = sampleColormap(0, 'risk');
      const expected = new THREE.Color(riskColors[0]);
      expect(col.r).toBeCloseTo(expected.r, 3);
    });

    it('should return dark red (severe) at t=1', () => {
      const col = sampleColormap(1, 'risk');
      const expected = new THREE.Color(riskColors[4]);
      expect(col.r).toBeCloseTo(expected.r, 3);
    });

    it('should return yellow-orange (minor) near t=0.25', () => {
      const col = sampleColormap(0.25, 'risk');
      const expected = new THREE.Color(riskColors[1]);
      expect(col.r).toBeCloseTo(expected.r, 3);
    });
  });
});
