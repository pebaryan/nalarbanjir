import {
  Component, inject, OnInit, OnDestroy, signal, effect,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { EMPTY, Subscription, interval } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';

import { ApiService } from '../../core/services/api.service';
import { SimulationStore } from '../../core/store/simulation.store';
import { LayerStore } from '../../core/store/layer.store';
import { TerrainViewerService, PickEvent } from '../../shared/components/terrain-viewer/terrain-viewer.service';
import { TerrainViewer } from '../../shared/components/terrain-viewer/terrain-viewer';
import { LayerPanel } from '../../shared/components/layer-panel/layer-panel';
import { SimulationPanel } from '../../shared/components/simulation-panel/simulation-panel';
import { InspectorPanel } from '../../shared/components/inspector-panel/inspector-panel';

@Component({
  selector: 'app-map',
  standalone: true,
  providers: [TerrainViewerService],  // scoped here so we can inject it directly
  imports: [CommonModule, TerrainViewer, LayerPanel, SimulationPanel, InspectorPanel],
  templateUrl: './map.html',
  styleUrl:    './map.scss',
})
export class MapPage implements OnInit, OnDestroy {
  private readonly api   = inject(ApiService);
  private readonly svc   = inject(TerrainViewerService);
  readonly simStore      = inject(SimulationStore);
  readonly layerStore    = inject(LayerStore);

  // HUD panel visibility
  readonly showLayers     = signal(true);
  readonly showSimulation = signal(true);

  // Inspector
  readonly pickEvent = signal<PickEvent | null>(null);

  // Raw grids from API (used to feed the viewer)
  private elevationGrid: number[][] | null = null;
  private subs: Subscription[] = [];

  constructor() {
    // React to layer config changes → update viewer styles
    effect(() => {
      const layers = this.layerStore.layers();
      for (const layer of layers) {
        this.svc.setLayerVisibility(layer.id, layer.visibility);
        this.svc.setLayerOpacity(layer.id, layer.opacity);
      }
    });
  }

  ngOnInit(): void {
    // Load existing layers from API
    this.layerStore.loadLayers();

    // Subscribe to map pick events
    this.subs.push(
      this.svc.pick$.subscribe(evt => this.pickEvent.set(evt)),
    );

    // Load terrain mesh and create/update DEM layer
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

    // Poll simulation state every 2 s — 409 = no engine yet, silently skip
    const poll = interval(2000).pipe(
      switchMap(() => this.api.getState().pipe(catchError(() => EMPTY))),
    ).subscribe({
      next: state => {
        if (!state.state_2d) return;
        const s2d = state.state_2d;
        const nx  = s2d.water_depth.length;
        const ny  = s2d.water_depth[0]?.length ?? 0;

        // Update stats
        if (state.stats) {
          this.simStore.updateFromStep(state.elapsed_time, state.current_step, {
            maxDepth: state.stats.max_depth, meanDepth: state.stats.mean_depth,
            floodedCells: state.stats.flooded_cells,
            floodedAreaKm2: state.stats.flooded_area_km2,
            dominantRisk: state.stats.dominant_risk as any,
          });
        }

        // Update flood depth layer (if visible in store)
        const fdLayer = this.layerStore.floodDepthLayer();
        if (fdLayer) {
          this.svc.setFloodLayer(
            'sim_flood_depth',
            { visibility: fdLayer.visibility, opacity: fdLayer.opacity, colormap: fdLayer.style.colormap,
              rangeMin: fdLayer.style.range_min, rangeMax: fdLayer.style.range_max, color: fdLayer.style.color },
            s2d.water_depth, this.elevationGrid,
            nx, ny,
            this.elevationGrid ? (this.elevationGrid[0] ? 100 : 100) : 100,
            100,
          );
        }

        // Update risk layer (if visible in store)
        const riskLayer = this.layerStore.floodRiskLayer();
        if (riskLayer && s2d.flood_risk) {
          this.svc.setRiskLayer(
            'sim_flood_risk',
            { visibility: riskLayer.visibility, opacity: riskLayer.opacity, colormap: 'risk',
              rangeMin: 0, rangeMax: 4, color: '#ef4444' },
            s2d.flood_risk, nx, ny, 100, 100, this.elevationGrid,
          );
        }
      },
      error: () => {},
    });
    this.subs.push(poll);
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
  }
}
