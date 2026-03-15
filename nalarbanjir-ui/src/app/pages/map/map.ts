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

  // Track which file_ids we've already fetched (avoid re-fetching on every signal change)
  private readonly loadedVectors = new Set<string>();
  private readonly loadedDems    = new Set<string>();

  // HUD panel visibility
  readonly showLayers     = signal(true);
  readonly showSimulation = signal(true);

  // Inspector
  readonly pickEvent = signal<PickEvent | null>(null);

  // 1D channel profile — shown when 1D state is available
  readonly channelData = signal<ChannelProfileData | null>(null);

  // Raw grids from API (used to feed the viewer)
  private elevationGrid: number[][] | null = null;
  private subs: Subscription[] = [];

  // Project import/export state
  readonly projectName    = signal('My Project');
  readonly projectMsg     = signal('');

  constructor() {
    effect(() => {
      const layers = this.layerStore.layers();
      for (const layer of layers) {
        this.svc.setLayerVisibility(layer.id, layer.visibility);
        this.svc.setLayerOpacity(layer.id, layer.opacity);

        // Load DEM layers from uploaded GeoTIFF/ASC files
        if (layer.type === 'dem'
            && layer.data_ref && !layer.data_ref.startsWith('sim:')
            && !this.loadedDems.has(layer.data_ref)) {
          this.loadedDems.add(layer.data_ref);
          this.layerApi.getGisElevation(layer.data_ref).subscribe({
            next: grid => {
              this.elevationGrid = grid.elevation;
              const worldBounds = {
                minX: grid.min_x, minY: grid.min_y,
                maxX: grid.max_x, maxY: grid.max_y,
              };
              this.svc.setDemLayer(
                layer.id,
                { visibility: layer.visibility, opacity: layer.opacity,
                  colormap: layer.style.colormap as any,
                  rangeMin: layer.style.range_min, rangeMax: layer.style.range_max,
                  color: layer.style.color },
                grid.elevation, grid.nx, grid.ny, grid.dx, grid.dy,
                worldBounds,
              );
              // Update layer metadata with real bounds
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
            error: () => {},
          });
        }

        // Load vector / building layers from backend when they first appear
        const isGeoLayer = (layer.type === 'vector' || layer.type === 'channel' || layer.type === 'building');
        if (isGeoLayer
            && layer.data_ref && !layer.data_ref.startsWith('sim:')
            && !this.loadedVectors.has(layer.data_ref)) {
          this.loadedVectors.add(layer.data_ref);

          const layerCfg = {
            visibility: layer.visibility,
            opacity:    layer.opacity,
            colormap:   layer.style.colormap,
            rangeMin:   layer.style.range_min,
            rangeMax:   layer.style.range_max,
            color:      layer.style.color,
          };

          if (layer.type === 'building') {
            this.layerApi.getBuildingsGeoJSON(layer.data_ref).subscribe({
              next: res => this.svc.setBuildingLayer(layer.id, layerCfg, res.geojson, res.bounds),
              error: () => {},
            });
          } else {
            this.layerApi.getVectorGeoJSON(layer.data_ref).subscribe({
              next: res => this.svc.setVectorLayer(layer.id, layerCfg, res.geojson, res.bounds),
              error: () => {},
            });
          }
        }
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

          const fdLayer = this.layerStore.floodDepthLayer();
          if (fdLayer) {
            this.svc.setFloodLayer(
              'sim_flood_depth',
              { visibility: fdLayer.visibility, opacity: fdLayer.opacity, colormap: fdLayer.style.colormap,
                rangeMin: fdLayer.style.range_min, rangeMax: fdLayer.style.range_max, color: fdLayer.style.color },
              s2d.water_depth, this.elevationGrid,
              nx, ny, 100, 100,
            );
          }

          const riskLayer = this.layerStore.floodRiskLayer();
          if (riskLayer && s2d.flood_risk) {
            this.svc.setRiskLayer(
              'sim_flood_risk',
              { visibility: riskLayer.visibility, opacity: riskLayer.opacity, colormap: 'risk',
                rangeMin: 0, rangeMax: 4, color: '#ef4444' },
              s2d.flood_risk, nx, ny, 100, 100, this.elevationGrid,
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
