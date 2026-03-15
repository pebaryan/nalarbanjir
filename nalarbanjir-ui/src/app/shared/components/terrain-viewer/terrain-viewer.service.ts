/**
 * TerrainViewerService
 *
 * Manages a Three.js scene inside a given <canvas> element.
 * Renders the simulation domain as a coloured height-map mesh.
 *
 * Lifecycle:
 *   1. init(canvas)      — attach renderer, build scene
 *   2. updateTerrain(z)  — upload elevation grid once
 *   3. updateWater(h)    — update water surface every step
 *   4. destroy()         — dispose all Three.js resources
 */
import { Injectable } from '@angular/core';
import * as THREE from 'three';

@Injectable()   // NOT providedIn:'root' — scoped to the component
export class TerrainViewerService {
  private renderer!: THREE.WebGLRenderer;
  private scene!:    THREE.Scene;
  private camera!:   THREE.PerspectiveCamera;
  private animId!:   number;

  private terrainMesh: THREE.Mesh | null = null;
  private waterMesh:   THREE.Mesh | null = null;

  private nx = 0;
  private ny = 0;
  private dx = 1;
  private dy = 1;

  // ── Setup ─────────────────────────────────────────────────────────────

  init(canvas: HTMLCanvasElement): void {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(devicePixelRatio);
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
    this.renderer.setClearColor(0x0f172a);

    this.scene  = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, canvas.clientWidth / canvas.clientHeight, 0.1, 1e6);

    // Ambient + directional light
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(1, 2, 1);
    this.scene.add(dir);

    this._startLoop();
  }

  // ── Terrain ───────────────────────────────────────────────────────────

  /**
   * Upload an (nx × ny) elevation grid and create the terrain mesh.
   * elevations is a flat row-major array [z(0,0), z(0,1), ..., z(nx-1,ny-1)].
   */
  updateTerrain(elevations: number[][], nx: number, ny: number, dx: number, dy: number): void {
    this.nx = nx;
    this.ny = ny;
    this.dx = dx;
    this.dy = dy;

    // Remove old mesh
    if (this.terrainMesh) {
      this.scene.remove(this.terrainMesh);
      this.terrainMesh.geometry.dispose();
    }

    const geom = this._buildHeightGeometry(elevations, nx, ny, dx, dy);
    const mat  = new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide });
    this.terrainMesh = new THREE.Mesh(geom, mat);
    this.scene.add(this.terrainMesh);

    this._positionCamera(nx * dx, ny * dy);
  }

  // ── Water surface ─────────────────────────────────────────────────────

  /**
   * Update the water surface mesh using the current depth grid.
   * Only cells with h > 0.001 m are shown.
   */
  updateWater(
    depths: number[][],
    bedElev: number[][] | null,
    nx: number, ny: number, dx: number, dy: number,
  ): void {
    if (this.waterMesh) {
      this.scene.remove(this.waterMesh);
      this.waterMesh.geometry.dispose();
    }

    const etaGrid: number[][] = depths.map((row, i) =>
      row.map((h, j) => (h > 0.001 ? (bedElev ? bedElev[i][j] : 0) + h : -999)),
    );

    const geom = this._buildHeightGeometry(etaGrid, nx, ny, dx, dy, true);
    const mat  = new THREE.MeshLambertMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.7,
      side: THREE.DoubleSide,
    });
    this.waterMesh = new THREE.Mesh(geom, mat);
    this.scene.add(this.waterMesh);
  }

  // ── Dispose ───────────────────────────────────────────────────────────

  destroy(): void {
    cancelAnimationFrame(this.animId);
    this.terrainMesh?.geometry.dispose();
    this.waterMesh?.geometry.dispose();
    this.renderer.dispose();
  }

  // ── Internal ──────────────────────────────────────────────────────────

  private _startLoop(): void {
    const loop = () => {
      this.animId = requestAnimationFrame(loop);
      this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  private _positionCamera(domainX: number, domainY: number): void {
    const cx = domainX / 2;
    const cy = domainY / 2;
    const dist = Math.max(domainX, domainY) * 0.8;
    this.camera.position.set(cx, dist, cy + dist * 0.5);
    this.camera.lookAt(cx, 0, cy);
  }

  private _buildHeightGeometry(
    grid: number[][], nx: number, ny: number, dx: number, dy: number,
    skipNegative = false,
  ): THREE.BufferGeometry {
    const positions: number[] = [];
    const colors: number[]    = [];
    const indices: number[]   = [];

    const color = new THREE.Color();
    const vIdx  = (i: number, j: number) => i * ny + j;

    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const z = grid[i]?.[j] ?? 0;
        positions.push(i * dx, z, j * dy);   // y-up convention → z is elevation
        // Height-based colour: terrain goes brown→green, water is blue
        const t = Math.max(0, Math.min(1, (z + 5) / 10));
        color.setHSL(0.08 + t * 0.25, 0.6, 0.3 + t * 0.2);
        colors.push(color.r, color.g, color.b);
      }
    }

    for (let i = 0; i < nx - 1; i++) {
      for (let j = 0; j < ny - 1; j++) {
        const a = vIdx(i,   j);
        const b = vIdx(i+1, j);
        const c = vIdx(i,   j+1);
        const d = vIdx(i+1, j+1);
        if (skipNegative) {
          const za = positions[a*3+1], zb = positions[b*3+1],
                zc = positions[c*3+1], zd = positions[d*3+1];
          if (za < -100 && zb < -100 && zc < -100 && zd < -100) continue;
        }
        indices.push(a, b, c,   b, d, c);
      }
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geom.setAttribute('color',    new THREE.Float32BufferAttribute(colors, 3));
    geom.setIndex(indices);
    geom.computeVertexNormals();
    return geom;
  }
}
