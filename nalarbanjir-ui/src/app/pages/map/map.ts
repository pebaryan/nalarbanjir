import {
  Component, inject, OnInit, OnDestroy, signal, effect,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { EMPTY, Subscription, interval } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';

import { ApiService } from '../../core/services/api.service';
import { SimulationStore } from '../../core/store/simulation.store';
import { LayerStore } from '../../core/store/layer.store';
import { LayerApiService } from '../../core/services/layer-api.service';
import { ProjectService } from '../../core/services/project.service';
import { TerrainViewerService, PickEvent } from '../../shared/components/terrain-viewer/terrain-viewer.service';
import { TerrainViewer } from '../../shared/components/terrain-viewer/terrain-viewer';
import { LayerPanel } from '../../shared/components/layer-panel/layer-panel';
import { SimulationPanel } from '../../shared/components/simulation-panel/simulation-panel';
import { InspectorPanel } from '../../shared/components/inspector-panel/inspector-panel';
import { ChannelProfile, ChannelProfileData } from '../../shared/components/channel-profile/channel-profile';

@Component({
  selector: 'app-map',
  standalone: true,
  providers: [TerrainViewerService],
  imports: [CommonModule, TerrainViewer, LayerPanel, SimulationPanel, InspectorPanel, ChannelProfile],
  templateUrl: './map.html',
  styleUrl:    './map.scss',
})
export class MapPage implements OnInit, OnDestroy {
  private readonly api        = inject(ApiService);
  private readonly layerApi   = inject(LayerApiService);
  private readonly svc        = inject(TerrainViewerService);
  private readonly project    = inject(ProjectService);
  readonly simStore           = inject(SimulationStore);
  readonly layerStore         = inject(LayerStore);

  // Cache fetched data so style changes re-render without a new network request
  private readonly elevationCache = new Map<string, {
    elevation: number[][]; nx: number; ny: number;
    dx: number; dy: number;
    min_x: number; min_y: number; max_x: number; max_y: number;
  }>();
  private readonly vectorCache = new Map<string, {
    geojson: any; bounds: { min_x: number; min_y: number; max_x: number; max_y: number };
    isBuilding: boolean;
  }>();
  // Last rendered style key per layer id — re-render when it changes
  private readonly styleKeys = new Map<string, string>();
  // IDs of layers currently present in the viewer scene
  private readonly renderedIds = new Set<string>();

  // HUD panel visibility
  readonly showLayers     = signal(true);
  readonly showSimulation = signal(true);

  // Inspector
  readonly pickEvent = signal<PickEvent | null>(null);

  // 1D channel profile — shown when 1D state is available
  readonly channelData = signal<ChannelProfileData | null>(null);

  // Raw grids from API (used to feed the viewer)
  private elevationGrid: number[][] | null = null;
  // Solver domain in metres — updated when terrain mesh is loaded after init
  private solverDomainX = 10000;
  private solverDomainY = 10000;
  private subs: Subscription[] = [];

  // Project import/export state
  readonly projectName    = signal('My Project');
  readonly projectMsg     = signal('');

  constructor() {
    // Re-fetch synthetic terrain mesh whenever the engine is re-initialized
    // so the 3D viewer shows the bowl terrain (not the flat pre-init placeholder)
    effect(() => {
      const count = this.simStore.initCount();
      if (count === 0) return;   // skip the initial value
      this.api.getTerrainMesh().subscribe(mesh => {
        this.elevationGrid = mesh.elevation;
        this.solverDomainX = mesh.nx * mesh.dx;
        this.solverDomainY = mesh.ny * mesh.dy;
        this.elevationCache.set('sim:terrain', {
          elevation: mesh.elevation, nx: mesh.nx, ny: mesh.ny,
          dx: mesh.dx, dy: mesh.dy,
          min_x: 0, min_y: 0, max_x: mesh.nx * mesh.dx, max_y: mesh.ny * mesh.dy,
        });
        // Force style re-render by clearing the cached style key
        this.styleKeys.delete('layer_terrain');
      });
    });

    effect(() => {
      const layers = this.layerStore.layers();
      const currentIds = new Set(layers.map(l => l.id));

      // Remove layers that are no longer in the store
      for (const id of this.renderedIds) {
        if (!currentIds.has(id)) {
          this.svc.removeLayer(id);
          this.styleKeys.delete(id);
          this.renderedIds.delete(id);
        }
      }

      for (const layer of layers) {
        this.svc.setLayerVisibility(layer.id, layer.visibility);
        this.svc.setLayerOpacity(layer.id, layer.opacity);

        const styleKey = `${layer.style.colormap}|${layer.style.range_min}|${layer.style.range_max}|${layer.style.color}`;
        const styleChanged = this.styleKeys.get(layer.id) !== styleKey;

        // ── DEM layers ──────────────────────────────────────────────
        if (layer.type === 'dem' && layer.data_ref) {
          const inCache = this.elevationCache.has(layer.data_ref);
          const cached  = this.elevationCache.get(layer.data_ref);
          if (inCache && cached) {
            // Data ready — re-render only when style changed
            if (styleChanged) {
              this.styleKeys.set(layer.id, styleKey);
              this.svc.setDemLayer(
                layer.id,
                { visibility: layer.visibility, opacity: layer.opacity,
                  colormap: layer.style.colormap as any,
                  rangeMin: layer.style.range_min, rangeMax: layer.style.range_max,
                  color: layer.style.color },
                cached.elevation, cached.nx, cached.ny, cached.dx, cached.dy,
                { minX: cached.min_x, minY: cached.min_y, maxX: cached.max_x, maxY: cached.max_y },
              );
            }
          } else if (!inCache && !layer.data_ref.startsWith('sim:')) {
            // Not yet fetched — mark in-flight, then fetch
            this.elevationCache.set(layer.data_ref, null as any);
            this.layerApi.getGisElevation(layer.data_ref).subscribe({
              next: grid => {
                this.elevationCache.set(layer.data_ref, grid);
                this.elevationGrid = grid.elevation;
                this.styleKeys.set(layer.id, styleKey);
                this.svc.setDemLayer(
                  layer.id,
                  { visibility: layer.visibility, opacity: layer.opacity,
                    colormap: layer.style.colormap as any,
                    rangeMin: layer.style.range_min, rangeMax: layer.style.range_max,
                    color: layer.style.color },
                  grid.elevation, grid.nx, grid.ny, grid.dx, grid.dy,
                  { minX: grid.min_x, minY: grid.min_y, maxX: grid.max_x, maxY: grid.max_y },
                );
                this.layerStore.upsertLocalLayer({
                  ...layer,
                  metadata: {
                    ...layer.metadata,
                    bounds: { min_x: grid.min_x, min_y: grid.min_y,
                              max_x: grid.max_x, max_y: grid.max_y },
                    resolution: [grid.dx, grid.dy],
                  },
                });
              },
              error: () => { this.elevationCache.delete(layer.data_ref); },
            });
          }
        }

        // ── Vector / building layers ─────────────────────────────────
        const isGeoLayer = (layer.type === 'vector' || layer.type === 'channel' || layer.type === 'building');
        if (isGeoLayer && layer.data_ref && !layer.data_ref.startsWith('sim:')) {
          const inCache = this.vectorCache.has(layer.data_ref);
          const cached  = this.vectorCache.get(layer.data_ref);
          const layerCfg = {
            visibility: layer.visibility, opacity: layer.opacity,
            colormap: layer.style.colormap, rangeMin: layer.style.range_min,
            rangeMax: layer.style.range_max, color: layer.style.color,
          };

          if (inCache && cached) {
            if (styleChanged) {
              this.styleKeys.set(layer.id, styleKey);
              if (cached.isBuilding) {
                this.svc.setBuildingLayer(layer.id, layerCfg, cached.geojson, cached.bounds);
              } else {
                this.svc.setVectorLayer(layer.id, layerCfg, cached.geojson, cached.bounds);
              }
            }
          } else if (!inCache) {
            this.vectorCache.set(layer.data_ref, null as any);
            const isBuilding = layer.type === 'building';
            const req$ = isBuilding
              ? this.layerApi.getBuildingsGeoJSON(layer.data_ref)
              : this.layerApi.getVectorGeoJSON(layer.data_ref);
            req$.subscribe({
              next: res => {
                this.vectorCache.set(layer.data_ref, { geojson: res.geojson, bounds: res.bounds, isBuilding });
                this.styleKeys.set(layer.id, styleKey);
                if (isBuilding) {
                  this.svc.setBuildingLayer(layer.id, layerCfg, res.geojson, res.bounds);
                } else {
                  this.svc.setVectorLayer(layer.id, layerCfg, res.geojson, res.bounds);
                }
              },
              error: () => { this.vectorCache.delete(layer.data_ref); },
            });
          }
        }

        this.renderedIds.add(layer.id);
      }
    });
  }

  ngOnInit(): void {
    this.layerStore.loadLayers();

    this.subs.push(
      this.svc.pick$.subscribe(evt => this.pickEvent.set(evt)),
    );

    this.api.getTerrainMesh().subscribe(mesh => {
      this.elevationGrid = mesh.elevation;
      this.solverDomainX = mesh.nx * mesh.dx;
      this.solverDomainY = mesh.ny * mesh.dy;
      // Cache synthetic terrain so style-change re-renders work for it too
      this.elevationCache.set('sim:terrain', {
        elevation: mesh.elevation, nx: mesh.nx, ny: mesh.ny,
        dx: mesh.dx, dy: mesh.dy,
        min_x: 0, min_y: 0, max_x: mesh.nx * mesh.dx, max_y: mesh.ny * mesh.dy,
      });
      const terrainLayer = {
        id: 'layer_terrain', name: 'Terrain DEM', type: 'dem' as const,
        visibility: true, opacity: 1.0, z_index: 0,
        data_ref: 'sim:terrain',
        style: { color: '#74c69d', colormap: 'terrain', range_min: null, range_max: null, line_width: 1.5, point_size: 4 },
        metadata: { crs_epsg: null, bounds: null, resolution: [mesh.dx, mesh.dy], feature_count: null, source_filename: 'synthetic' },
      };
      this.layerStore.upsertLocalLayer(terrainLayer);
      this.svc.setDemLayer(
        'layer_terrain',
        { visibility: true, opacity: 1.0, colormap: 'terrain', rangeMin: null, rangeMax: null, color: '#74c69d' },
        mesh.elevation, mesh.nx, mesh.ny, mesh.dx, mesh.dy,
      );
    });

    // Poll simulation state every 2 s
    const poll = interval(2000).pipe(
      switchMap(() => this.api.getState().pipe(catchError(() => EMPTY))),
    ).subscribe({
      next: state => {
        // ── 2D state ──────────────────────────────────────────────────
        if (state.state_2d) {
          const s2d = state.state_2d;
          const nx  = s2d.water_depth.length;
          const ny  = s2d.water_depth[0]?.length ?? 0;

          if (state.stats) {
            this.simStore.updateFromStep(state.elapsed_time, state.current_step, {
              maxDepth: state.stats.max_depth, meanDepth: state.stats.mean_depth,
              floodedCells: state.stats.flooded_cells,
              floodedAreaKm2: state.stats.flooded_area_km2,
              dominantRisk: state.stats.dominant_risk as any,
            });
          }

          // dx/dy derived from solver domain so flood overlay covers the same
          // extent as the terrain mesh (whether synthetic or DEM-backed)
          const floodDx = this.solverDomainX / nx;
          const floodDy = this.solverDomainY / ny;

          const fdLayer = this.layerStore.floodDepthLayer();
          if (fdLayer) {
            this.svc.setFloodLayer(
              'sim_flood_depth',
              { visibility: fdLayer.visibility, opacity: fdLayer.opacity, colormap: fdLayer.style.colormap,
                rangeMin: fdLayer.style.range_min, rangeMax: fdLayer.style.range_max, color: fdLayer.style.color },
              s2d.water_depth, this.elevationGrid,
              nx, ny, floodDx, floodDy,
            );
          }

          const riskLayer = this.layerStore.floodRiskLayer();
          if (riskLayer && s2d.flood_risk) {
            this.svc.setRiskLayer(
              'sim_flood_risk',
              { visibility: riskLayer.visibility, opacity: riskLayer.opacity, colormap: 'risk',
                rangeMin: 0, rangeMax: 4, color: '#ef4444' },
              s2d.flood_risk, nx, ny, floodDx, floodDy, this.elevationGrid,
            );
          }
        }

        // ── 1D state ──────────────────────────────────────────────────
        if (state.state_1d) {
          const s1d = state.state_1d;
          // Reconstruct bed elevation from water surface - (approximate: use min water as bed proxy
          // Real bed elevation comes from the cross-section z_bed; server could expose it.
          // For now, compute bed as water_surface - a fixed bank height offset when depth > 0.
          // The channel profile viewer just needs relative shape, so this is sufficient.
          const bedElev = s1d.water_surface_elev.map((ws, i) => {
            // bed = water surface minus typical bankfull depth (rough estimate from discharge)
            const q = s1d.discharge[i] ?? 0;
            const approxDepth = Math.max(q / (20 * 1.5), 0); // Q / (width * V_est)
            return ws - approxDepth;
          });
          this.channelData.set({
            chainage:          s1d.chainage,
            bedElev,
            waterSurfaceElev:  s1d.water_surface_elev,
            discharge:         s1d.discharge,
          });
          if (!state.state_2d && state.stats) {
            this.simStore.updateFromStep(state.elapsed_time, state.current_step, null);
          }
        } else {
          // Clear channel profile when not in 1D mode
          if (this.channelData() !== null) this.channelData.set(null);
        }
      },
      error: () => {},
    });
    this.subs.push(poll);
  }

  exportProject(): void {
    this.project.export(this.projectName(), {
      mode:    '2d',
      steps:   500,
      rainfall: { pattern: 'uniform', intensity_mm_hr: 0, duration_min: 60 },
    });
  }

  importProject(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.project.import(file).then(simCfg => {
      this.projectMsg.set(`Loaded: ${file.name}`);
      setTimeout(() => this.projectMsg.set(''), 3000);
    }).catch(err => {
      this.projectMsg.set(`Import failed: ${(err as Error).message}`);
    });
    (event.target as HTMLInputElement).value = '';
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
  }
}
