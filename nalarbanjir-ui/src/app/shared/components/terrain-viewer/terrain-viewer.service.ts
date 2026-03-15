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
import { GeoJSONFeatureCollection } from '../../../core/services/layer-api.service';

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

  private readonly raycaster    = new THREE.Raycaster();
  private readonly layerMeshes  = new Map<string, THREE.Mesh>();
  private readonly layerLines   = new Map<string, THREE.LineSegments>();
  private readonly meshToLayer  = new Map<THREE.Object3D, string>();

  private nx = 100;
  private ny = 100;
  private dx = 100;
  private dy = 100;

  // World bounds of the currently active DEM (for vector coordinate mapping)
  private demBounds: { minX: number; minY: number; maxX: number; maxY: number } | null = null;

  private orbit = { theta: 0.8, phi: 1.0, radius: 8000, targetX: 0, targetZ: 0 };
  private drag  = { active: false, pan: false, lastX: 0, lastY: 0, downX: 0, downY: 0 };
  private touch = { lastDist: 0, lastMidX: 0, lastMidY: 0 };

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
    this.layerLines.forEach(l => { l.geometry.dispose(); (l.material as THREE.Material).dispose(); });
    this.layerMeshes.clear();
    this.layerLines.clear();
    this.meshToLayer.clear();
    this.renderer?.dispose();
    this.pick$.complete();
    window.removeEventListener('resize', () => this.resize());
  }

  // ── Layer rendering ─────────────────────────────────────────────────────

  setDemLayer(
    id: string, cfg: LayerRenderConfig,
    elevation: number[][], nx: number, ny: number, dx: number, dy: number,
    worldBounds?: { minX: number; minY: number; maxX: number; maxY: number } | null,
  ): void {
    this.nx = nx; this.ny = ny; this.dx = dx; this.dy = dy;
    if (worldBounds) this.demBounds = worldBounds;
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

    const bedR = bed ? this._resampleElev(bed, nx, ny) : null;
    const eta = depth.map((row, i) =>
      row.map((h, j) => h > 0.001 ? (bedR ? (bedR[i]?.[j] ?? 0) : 0) + h : -9999),
    );
    const valid = eta.flat().filter(v => v > -9999);
    if (valid.length === 0) return;

    const min = cfg.rangeMin ?? Math.min(...valid);
    const max = cfg.rangeMax ?? Math.max(...valid);

    const geom = this._buildGeom(eta, nx, ny, dx, dy, min, max, 'blues', true);
    const mat  = new THREE.MeshLambertMaterial({
      vertexColors: true, transparent: true,
      opacity: cfg.opacity * 0.75, side: THREE.DoubleSide,
      polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
    });
    const mesh = this._addMesh(id, geom, mat, cfg);
    mesh.position.y = 1.0;
  }

  setRiskLayer(
    id: string, cfg: LayerRenderConfig,
    risk: number[][], nx: number, ny: number, dx: number, dy: number,
    elevation?: number[][] | null,
  ): void {
    this._removeMesh(id);
    const elevR = elevation ? this._resampleElev(elevation, nx, ny) : null;
    const base  = elevR ?? risk.map(row => row.map(() => 0));
    const geom  = this._buildGeom(base, nx, ny, dx, dy, 0, 4, 'risk', false, risk);
    const mat   = new THREE.MeshLambertMaterial({
      vertexColors: true, transparent: true,
      opacity: cfg.opacity * 0.8, side: THREE.DoubleSide,
      polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
    });
    const mesh = this._addMesh(id, geom, mat, cfg);
    mesh.position.y = 2.0;
  }

  removeLayer(id: string): void {
    this._removeMesh(id);
    this._removeLines(id);
  }

  setLayerVisibility(id: string, visible: boolean): void {
    const m = this.layerMeshes.get(id);
    if (m) m.visible = visible;
    const l = this.layerLines.get(id);
    if (l) l.visible = visible;
  }

  setLayerOpacity(id: string, opacity: number): void {
    const m = this.layerMeshes.get(id);
    if (m) {
      const mat = m.material as THREE.MeshLambertMaterial;
      mat.opacity = opacity; mat.transparent = opacity < 1; mat.needsUpdate = true;
    }
    const l = this.layerLines.get(id);
    if (l) {
      const mat = l.material as THREE.LineBasicMaterial;
      mat.opacity = opacity; mat.transparent = opacity < 1; mat.needsUpdate = true;
    }
  }

  /**
   * Render a GeoJSON vector layer as lines on top of the terrain.
   * Coordinates are mapped from world-space (DEM CRS) to scene space.
   * If no DEM bounds are known, coordinates are treated as scene-local.
   */
  setVectorLayer(
    id: string,
    cfg: LayerRenderConfig,
    geojson: GeoJSONFeatureCollection,
    vectorBounds: { min_x: number; min_y: number; max_x: number; max_y: number },
  ): void {
    this._removeLines(id);

    const pts: number[] = [];
    const sceneW = this.nx * this.dx;
    const sceneH = this.ny * this.dy;

    // Determine coordinate transform: map [minX..maxX] × [minY..maxY] → [0..sceneW] × [0..sceneH]
    // Prefer aligning to DEM bounds when available; fall back to vector's own bounds.
    const srcBounds = this.demBounds
      ? { minX: this.demBounds.minX, minY: this.demBounds.minY,
          maxX: this.demBounds.maxX, maxY: this.demBounds.maxY }
      : { minX: vectorBounds.min_x, minY: vectorBounds.min_y,
          maxX: vectorBounds.max_x, maxY: vectorBounds.max_y };

    const rangeX = srcBounds.maxX - srcBounds.minX || 1;
    const rangeY = srcBounds.maxY - srcBounds.minY || 1;

    const toScene = (x: number, y: number): [number, number] => [
      ((x - srcBounds.minX) / rangeX) * sceneW,
      ((y - srcBounds.minY) / rangeY) * sceneH,
    ];

    // Walk all features and extract line/ring segments
    const pushLine = (coords: number[][]) => {
      for (let i = 0; i < coords.length - 1; i++) {
        const [ax, az] = toScene(coords[i][0], coords[i][1]);
        const [bx, bz] = toScene(coords[i + 1][0], coords[i + 1][1]);
        pts.push(ax, 0.5, az, bx, 0.5, bz);   // y=0.5 floats slightly above terrain
      }
    };

    for (const feat of geojson.features) {
      if (!feat.geometry) continue;
      const g = feat.geometry;
      switch (g.type) {
        case 'LineString':      pushLine(g.coordinates as number[][]); break;
        case 'MultiLineString': (g.coordinates as number[][][]).forEach(pushLine); break;
        case 'Polygon':         (g.coordinates as number[][][]).forEach(pushLine); break;
        case 'MultiPolygon':    (g.coordinates as number[][][][]).forEach(rings => rings.forEach(pushLine)); break;
        case 'Point': {
          const [px, pz] = toScene((g.coordinates as number[])[0], (g.coordinates as number[])[1]);
          pts.push(px - 5, 0.5, pz, px + 5, 0.5, pz);
          break;
        }
      }
    }

    if (pts.length === 0) return;

    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));

    const color = new THREE.Color(cfg.color || '#38bdf8');
    const mat   = new THREE.LineBasicMaterial({
      color,
      transparent: cfg.opacity < 1,
      opacity:     cfg.opacity,
      linewidth:   1,   // >1 only works in WebGL2 with linewidth extension
    });

    const lines      = new THREE.LineSegments(geom, mat);
    lines.visible    = cfg.visibility;
    this.scene.add(lines);
    this.layerLines.set(id, lines);
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

  /**
   * Render a CityGML building layer as extruded 3D footprints.
   * GeoJSON features must have a `height` property (metres).
   * Coordinates are mapped to scene space the same way as vector layers.
   */
  setBuildingLayer(
    id: string,
    cfg: LayerRenderConfig,
    geojson: GeoJSONFeatureCollection,
    vectorBounds: { min_x: number; min_y: number; max_x: number; max_y: number },
  ): void {
    this._removeMesh(id);

    const sceneW = this.nx * this.dx;
    const sceneH = this.ny * this.dy;

    const srcBounds = this.demBounds
      ? { minX: this.demBounds.minX, minY: this.demBounds.minY,
          maxX: this.demBounds.maxX, maxY: this.demBounds.maxY }
      : { minX: vectorBounds.min_x, minY: vectorBounds.min_y,
          maxX: vectorBounds.max_x, maxY: vectorBounds.max_y };

    const rangeX = srcBounds.maxX - srcBounds.minX || 1;
    const rangeY = srcBounds.maxY - srcBounds.minY || 1;

    const toScene = (x: number, y: number): [number, number] => [
      ((x - srcBounds.minX) / rangeX) * sceneW,
      ((y - srcBounds.minY) / rangeY) * sceneH,
    ];

    // Merge all buildings into a single geometry for performance
    const positions: number[] = [];
    const indices:   number[] = [];
    const colors:    number[] = [];
    let baseVertex = 0;

    const wallColor  = new THREE.Color(cfg.color || '#d4a96a');
    const roofColor  = new THREE.Color(cfg.color || '#d4a96a').multiplyScalar(0.8);

    for (const feat of geojson.features) {
      if (!feat.geometry) continue;
      const height = (feat.properties?.['height'] as number) ?? 10;
      if (height <= 0) continue;

      const ringsList: number[][][] = [];
      const g = feat.geometry;

      if (g.type === 'Polygon') {
        ringsList.push(g.coordinates[0] as number[][]);  // outer ring only
      } else if (g.type === 'MultiPolygon') {
        for (const poly of g.coordinates as number[][][][]) {
          ringsList.push(poly[0]);
        }
      }

      for (const ring of ringsList) {
        if (ring.length < 3) continue;

        const pts: Array<[number, number]> = ring.map(c => toScene(c[0], c[1]));
        const n = pts.length;
        const baseY = 0;
        const topY  = height;

        // Bottom ring
        for (const [x, z] of pts) {
          positions.push(x, baseY, z);
          colors.push(wallColor.r, wallColor.g, wallColor.b);
        }
        // Top ring
        for (const [x, z] of pts) {
          positions.push(x, topY, z);
          colors.push(roofColor.r, roofColor.g, roofColor.b);
        }

        // Side walls
        for (let i = 0; i < n; i++) {
          const j  = (i + 1) % n;
          const b0 = baseVertex + i,       b1 = baseVertex + j;
          const t0 = baseVertex + i + n,   t1 = baseVertex + j + n;
          indices.push(b0, b1, t0, b1, t1, t0);
        }

        // Roof cap (simple fan from first top vertex)
        for (let i = 1; i < n - 1; i++) {
          indices.push(
            baseVertex + n,
            baseVertex + n + i,
            baseVertex + n + i + 1,
          );
        }

        baseVertex += n * 2;
      }
    }

    if (positions.length === 0) return;

    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geom.setAttribute('color',    new THREE.Float32BufferAttribute(colors, 3));
    geom.setIndex(indices);
    geom.computeVertexNormals();

    const mat = new THREE.MeshLambertMaterial({
      vertexColors: true,
      transparent:  cfg.opacity < 1,
      opacity:      cfg.opacity,
      side:         THREE.DoubleSide,
    });
    this._addMesh(id, geom, mat, cfg);
  }

  private _removeLines(id: string): void {
    const l = this.layerLines.get(id);
    if (!l) return;
    this.scene.remove(l);
    l.geometry.dispose();
    (l.material as THREE.Material).dispose();
    this.layerLines.delete(id);
  }

  /** Nearest-neighbour resample of a 2-D grid to (targetNx × targetNy). */
  private _resampleElev(elev: number[][], targetNx: number, targetNy: number): number[][] {
    const srcNx = elev.length;
    const srcNy = elev[0]?.length ?? 0;
    if (srcNx === targetNx && srcNy === targetNy) return elev;
    return Array.from({ length: targetNx }, (_, i) => {
      const si = Math.min(srcNx - 1, Math.floor(i * srcNx / targetNx));
      return Array.from({ length: targetNy }, (_, j) => {
        const sj = Math.min(srcNy - 1, Math.floor(j * srcNy / targetNy));
        return elev[si]?.[sj] ?? 0;
      });
    });
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
    // ── Mouse ──────────────────────────────────────────────────────────────
    canvas.addEventListener('mousedown', e => {
      // left=0 → rotate | middle=1 or right=2 → pan
      const pan = e.button === 1 || e.button === 2;
      this.drag = { active: true, pan, lastX: e.clientX, lastY: e.clientY, downX: e.clientX, downY: e.clientY };
      canvas.style.cursor = pan ? 'move' : 'grabbing';
    });

    canvas.addEventListener('mousemove', e => {
      if (!this.drag.active) return;
      const dx = e.clientX - this.drag.lastX;
      const dy = e.clientY - this.drag.lastY;
      this.drag.lastX = e.clientX;
      this.drag.lastY = e.clientY;

      if (this.drag.pan) {
        this._pan(dx, dy);
      } else {
        this.orbit.theta -= dx * 0.007;
        this.orbit.phi    = Math.max(0.05, Math.min(Math.PI / 2 - 0.02, this.orbit.phi - dy * 0.007));
      }
      this._applyOrbit();
    });

    const stop = () => {
      this.drag.active = false;
      canvas.style.cursor = 'grab';
    };
    canvas.addEventListener('mouseup',    stop);
    canvas.addEventListener('mouseleave', stop);

    canvas.addEventListener('wheel', e => {
      e.preventDefault();
      this.orbit.radius = Math.max(50, Math.min(2e5, this.orbit.radius * (1 + e.deltaY * 0.001)));
      this._applyOrbit();
    }, { passive: false });

    canvas.addEventListener('contextmenu', e => e.preventDefault());

    // ── Touch ──────────────────────────────────────────────────────────────
    canvas.addEventListener('touchstart', e => {
      e.preventDefault();
      if (e.touches.length === 1) {
        const t = e.touches[0];
        this.drag = { active: true, pan: false, lastX: t.clientX, lastY: t.clientY, downX: t.clientX, downY: t.clientY };
      } else if (e.touches.length === 2) {
        this.drag.active = false;
        const [a, b] = [e.touches[0], e.touches[1]];
        this.touch.lastDist = Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
        this.touch.lastMidX = (a.clientX + b.clientX) / 2;
        this.touch.lastMidY = (a.clientY + b.clientY) / 2;
      }
    }, { passive: false });

    canvas.addEventListener('touchmove', e => {
      e.preventDefault();
      if (e.touches.length === 1 && this.drag.active) {
        const t = e.touches[0];
        const dx = t.clientX - this.drag.lastX;
        const dy = t.clientY - this.drag.lastY;
        this.drag.lastX = t.clientX;
        this.drag.lastY = t.clientY;
        this.orbit.theta -= dx * 0.007;
        this.orbit.phi    = Math.max(0.05, Math.min(Math.PI / 2 - 0.02, this.orbit.phi - dy * 0.007));
        this._applyOrbit();
      } else if (e.touches.length === 2) {
        const [a, b] = [e.touches[0], e.touches[1]];
        const dist   = Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
        const midX   = (a.clientX + b.clientX) / 2;
        const midY   = (a.clientY + b.clientY) / 2;

        // Pinch → zoom
        if (this.touch.lastDist > 0) {
          this.orbit.radius = Math.max(50, Math.min(2e5, this.orbit.radius * (this.touch.lastDist / dist)));
        }
        // Two-finger drag → pan
        this._pan(midX - this.touch.lastMidX, midY - this.touch.lastMidY);

        this.touch.lastDist = dist;
        this.touch.lastMidX = midX;
        this.touch.lastMidY = midY;
        this._applyOrbit();
      }
    }, { passive: false });

    canvas.addEventListener('touchend', () => { this.drag.active = false; this.touch.lastDist = 0; });

    canvas.style.cursor = 'grab';
    this._applyOrbit();
  }

  private _pan(dxPx: number, dyPx: number): void {
    const s = this.orbit.radius * 0.0012;
    // Camera right in XZ = (cos θ, −sin θ)
    this.orbit.targetX += dxPx * s * Math.cos(this.orbit.theta);
    this.orbit.targetZ -= dxPx * s * Math.sin(this.orbit.theta);
    // Screen-up projected to XZ = (−sin θ · cos φ, −cos θ · cos φ)
    // Drag down (dyPx > 0) → move target in −screenUp direction
    this.orbit.targetX += dyPx * s * Math.sin(this.orbit.theta) * Math.cos(this.orbit.phi);
    this.orbit.targetZ += dyPx * s * Math.cos(this.orbit.theta) * Math.cos(this.orbit.phi);
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
