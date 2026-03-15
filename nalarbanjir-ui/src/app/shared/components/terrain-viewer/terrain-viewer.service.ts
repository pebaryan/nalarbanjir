/**
 * TerrainViewerService  — layer-driven Three.js scene manager.
 *
 * Provided at MapPage level so the page can call rendering methods directly.
 *
 * Public API:
 *   init(canvas)
 *   setDemLayer(id, cfg, elevation, nx, ny, dx, dy)
 *   setFloodLayer(id, cfg, depth, bed, nx, ny, dx, dy)
 *   setRiskLayer(id, cfg, risk, nx, ny, dx, dy, elevation?)
 *   removeLayer(id)
 *   setLayerVisibility(id, visible)
 *   setLayerOpacity(id, opacity)
 *   pick$  — Subject<PickEvent> emitted on map clicks
 *   resize()
 *   destroy()
 */
import { Injectable } from '@angular/core';
import * as THREE from 'three';
import { Subject } from 'rxjs';
import { sampleColormap, ColormapName } from '../../utils/colormap';

export interface LayerRenderConfig {
  visibility: boolean;
  opacity:    number;
  colormap:   string;
  rangeMin:   number | null;
  rangeMax:   number | null;
  color:      string;
}

export interface PickEvent {
  worldX:    number;
  worldZ:    number;
  gridI:     number;
  gridJ:     number;
  elevation: number;
  layerId:   string;
}

@Injectable()
export class TerrainViewerService {
  private renderer!: THREE.WebGLRenderer;
  private scene!:    THREE.Scene;
  private camera!:   THREE.PerspectiveCamera;
  private animId!:   number;
  private canvas!:   HTMLCanvasElement;

  private readonly raycaster   = new THREE.Raycaster();
  private readonly layerMeshes = new Map<string, THREE.Mesh>();
  private readonly meshToLayer = new Map<THREE.Object3D, string>();

  private nx = 100;
  private ny = 100;
  private dx = 100;
  private dy = 100;

  private orbit = { theta: 0.8, phi: 1.0, radius: 8000, targetX: 0, targetZ: 0 };
  private drag   = { active: false, right: false, lastX: 0, lastY: 0, downX: 0, downY: 0 };

  readonly pick$ = new Subject<PickEvent>();

  // ── Lifecycle ────────────────────────────────────────────────────────────

  init(canvas: HTMLCanvasElement): void {
    this.canvas = canvas;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
    this.renderer.setClearColor(0x0a1628);

    this.scene  = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, canvas.clientWidth / canvas.clientHeight, 1, 5e5);

    // Lighting
    this.scene.add(new THREE.AmbientLight(0xd0e4f7, 0.55));
    const sun = new THREE.DirectionalLight(0xfff8e7, 1.1);
    sun.position.set(1, 2, 0.6);
    this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0x7aa8d4, 0.25);
    fill.position.set(-1, 0.5, -1);
    this.scene.add(fill);

    this._setupOrbit(canvas);
    this._setupRaycaster(canvas);
    this._loop();

    window.addEventListener('resize', () => this.resize());
  }

  resize(): void {
    if (!this.canvas) return;
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  destroy(): void {
    cancelAnimationFrame(this.animId);
    this.layerMeshes.forEach(m => { m.geometry.dispose(); (m.material as THREE.Material).dispose(); });
    this.layerMeshes.clear();
    this.meshToLayer.clear();
    this.renderer?.dispose();
    this.pick$.complete();
    window.removeEventListener('resize', () => this.resize());
  }

  // ── Layer rendering ─────────────────────────────────────────────────────

  setDemLayer(
    id: string, cfg: LayerRenderConfig,
    elevation: number[][], nx: number, ny: number, dx: number, dy: number,
  ): void {
    this.nx = nx; this.ny = ny; this.dx = dx; this.dy = dy;
    this._removeMesh(id);

    const flat = elevation.flat();
    const min  = cfg.rangeMin ?? Math.min(...flat);
    const max  = cfg.rangeMax ?? Math.max(...flat);

    const geom = this._buildGeom(elevation, nx, ny, dx, dy, min, max, cfg.colormap as ColormapName);
    const mat  = new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide });
    this._addMesh(id, geom, mat, cfg);
    this._fitCamera(nx * dx, ny * dy);
  }

  setFloodLayer(
    id: string, cfg: LayerRenderConfig,
    depth: number[][], bed: number[][] | null,
    nx: number, ny: number, dx: number, dy: number,
  ): void {
    this._removeMesh(id);

    const eta = depth.map((row, i) =>
      row.map((h, j) => h > 0.001 ? (bed ? bed[i][j] : 0) + h : -9999),
    );
    const valid = eta.flat().filter(v => v > -9999);
    if (valid.length === 0) return;

    const min = cfg.rangeMin ?? Math.min(...valid);
    const max = cfg.rangeMax ?? Math.max(...valid);

    const geom = this._buildGeom(eta, nx, ny, dx, dy, min, max, 'blues', true);
    const mat  = new THREE.MeshLambertMaterial({
      vertexColors: true, transparent: true,
      opacity: cfg.opacity * 0.75, side: THREE.DoubleSide,
    });
    const mesh = this._addMesh(id, geom, mat, cfg);
    mesh.position.y = 0.15;
  }

  setRiskLayer(
    id: string, cfg: LayerRenderConfig,
    risk: number[][], nx: number, ny: number, dx: number, dy: number,
    elevation?: number[][] | null,
  ): void {
    this._removeMesh(id);
    const base = elevation ?? risk.map(row => row.map(() => 0));
    const geom = this._buildGeom(base, nx, ny, dx, dy, 0, 4, 'risk', false, risk);
    const mat  = new THREE.MeshLambertMaterial({
      vertexColors: true, transparent: true,
      opacity: cfg.opacity * 0.8, side: THREE.DoubleSide,
    });
    const mesh = this._addMesh(id, geom, mat, cfg);
    mesh.position.y = 0.3;
  }

  removeLayer(id: string): void { this._removeMesh(id); }

  setLayerVisibility(id: string, visible: boolean): void {
    const m = this.layerMeshes.get(id);
    if (m) m.visible = visible;
  }

  setLayerOpacity(id: string, opacity: number): void {
    const m = this.layerMeshes.get(id);
    if (!m) return;
    const mat = m.material as THREE.MeshLambertMaterial;
    mat.opacity      = opacity;
    mat.transparent  = opacity < 1;
    mat.needsUpdate  = true;
  }

  // ── Private helpers ─────────────────────────────────────────────────────

  private _addMesh(
    id: string,
    geom: THREE.BufferGeometry,
    mat: THREE.MeshLambertMaterial,
    cfg: LayerRenderConfig,
  ): THREE.Mesh {
    const mesh    = new THREE.Mesh(geom, mat);
    mesh.visible  = cfg.visibility;
    mat.opacity   = cfg.opacity;
    mat.transparent = cfg.opacity < 1;
    this.scene.add(mesh);
    this.layerMeshes.set(id, mesh);
    this.meshToLayer.set(mesh, id);
    return mesh;
  }

  private _removeMesh(id: string): void {
    const m = this.layerMeshes.get(id);
    if (!m) return;
    this.scene.remove(m);
    m.geometry.dispose();
    (m.material as THREE.Material).dispose();
    this.meshToLayer.delete(m);
    this.layerMeshes.delete(id);
  }

  private _buildGeom(
    grid: number[][], nx: number, ny: number, dx: number, dy: number,
    minVal: number, maxVal: number, colormap: ColormapName,
    skipInvalid = false,
    colorGrid:   number[][] | null = null,
  ): THREE.BufferGeometry {
    const positions: number[] = [];
    const colors:    number[] = [];
    const indices:   number[] = [];
    const range = (maxVal - minVal) || 1;
    const vIdx  = (i: number, j: number) => i * ny + j;

    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const z = grid[i]?.[j] ?? 0;
        positions.push(i * dx, z, j * dy);
        const cVal = colorGrid ? (colorGrid[i]?.[j] ?? 0) : z;
        const col  = sampleColormap((cVal - minVal) / range, colormap);
        colors.push(col.r, col.g, col.b);
      }
    }

    for (let i = 0; i < nx - 1; i++) {
      for (let j = 0; j < ny - 1; j++) {
        const a = vIdx(i, j), b = vIdx(i + 1, j),
              c = vIdx(i, j + 1), d = vIdx(i + 1, j + 1);
        if (skipInvalid) {
          if (positions[a*3+1] < -100 && positions[b*3+1] < -100 &&
              positions[c*3+1] < -100 && positions[d*3+1] < -100) continue;
        }
        indices.push(a, b, c, b, d, c);
      }
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geom.setAttribute('color',    new THREE.Float32BufferAttribute(colors, 3));
    geom.setIndex(indices);
    geom.computeVertexNormals();
    return geom;
  }

  private _fitCamera(domainX: number, domainY: number): void {
    this.orbit.targetX = domainX / 2;
    this.orbit.targetZ = domainY / 2;
    this.orbit.radius  = Math.max(domainX, domainY) * 1.1;
    this._applyOrbit();
  }

  private _applyOrbit(): void {
    const { theta, phi, radius, targetX, targetZ } = this.orbit;
    this.camera.position.set(
      targetX + radius * Math.sin(phi) * Math.sin(theta),
      radius  * Math.cos(phi),
      targetZ + radius * Math.sin(phi) * Math.cos(theta),
    );
    this.camera.lookAt(targetX, 0, targetZ);
  }

  // ── Orbit controls (no external library) ───────────────────────────────

  private _setupOrbit(canvas: HTMLCanvasElement): void {
    canvas.addEventListener('mousedown', e => {
      this.drag = { active: true, right: e.button === 2, lastX: e.clientX, lastY: e.clientY, downX: e.clientX, downY: e.clientY };
    });

    canvas.addEventListener('mousemove', e => {
      if (!this.drag.active) return;
      const dxM = e.clientX - this.drag.lastX;
      const dyM = e.clientY - this.drag.lastY;
      this.drag.lastX = e.clientX;
      this.drag.lastY = e.clientY;

      if (this.drag.right) {
        const s = this.orbit.radius * 0.0012;
        this.orbit.targetX -= dxM * s * Math.cos(this.orbit.theta);
        this.orbit.targetZ -= dxM * s * Math.sin(this.orbit.theta);
        this.orbit.targetX += dyM * s * Math.sin(this.orbit.theta) * Math.cos(this.orbit.phi);
        this.orbit.targetZ -= dyM * s * Math.cos(this.orbit.theta) * Math.cos(this.orbit.phi);
      } else {
        this.orbit.theta -= dxM * 0.007;
        this.orbit.phi    = Math.max(0.05, Math.min(Math.PI / 2 - 0.02, this.orbit.phi - dyM * 0.007));
      }
      this._applyOrbit();
    });

    const stop = () => { this.drag.active = false; };
    canvas.addEventListener('mouseup',    stop);
    canvas.addEventListener('mouseleave', stop);

    canvas.addEventListener('wheel', e => {
      e.preventDefault();
      this.orbit.radius = Math.max(50, Math.min(2e5, this.orbit.radius * (1 + e.deltaY * 0.001)));
      this._applyOrbit();
    }, { passive: false });

    canvas.addEventListener('contextmenu', e => e.preventDefault());
    this._applyOrbit();
  }

  // ── Raycasting (click-to-inspect) ───────────────────────────────────────

  private _setupRaycaster(canvas: HTMLCanvasElement): void {
    canvas.addEventListener('click', e => {
      if (Math.hypot(e.clientX - this.drag.downX, e.clientY - this.drag.downY) > 5) return;

      const rect = canvas.getBoundingClientRect();
      this.raycaster.setFromCamera(
        new THREE.Vector2(
          ((e.clientX - rect.left) / rect.width)  * 2 - 1,
          ((e.clientY - rect.top)  / rect.height) * -2 + 1,
        ),
        this.camera,
      );

      const hits = this.raycaster.intersectObjects([...this.layerMeshes.values()], false);
      if (hits.length > 0) {
        const pt = hits[0].point;
        this.pick$.next({
          worldX:    pt.x,
          worldZ:    pt.z,
          gridI:     Math.round(pt.x / this.dx),
          gridJ:     Math.round(pt.z / this.dy),
          elevation: pt.y,
          layerId:   this.meshToLayer.get(hits[0].object) ?? '',
        });
      }
    });
  }

  private _loop(): void {
    const tick = () => {
      this.animId = requestAnimationFrame(tick);
      this.renderer.render(this.scene, this.camera);
    };
    tick();
  }
}
