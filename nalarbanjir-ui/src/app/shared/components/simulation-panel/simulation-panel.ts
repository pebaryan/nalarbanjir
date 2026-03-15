import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { filter } from 'rxjs/operators';
import { ApiService, SimulationMode } from '../../../core/services/api.service';
import { WebSocketService } from '../../../core/services/websocket.service';
import { SimulationStore } from '../../../core/store/simulation.store';
import { LayerStore } from '../../../core/store/layer.store';

@Component({
  selector: 'app-simulation-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './simulation-panel.html',
  styleUrl:    './simulation-panel.scss',
})
export class SimulationPanel implements OnInit, OnDestroy {
  private readonly api     = inject(ApiService);
  private readonly ws      = inject(WebSocketService);
  readonly store           = inject(SimulationStore);
  private readonly layers  = inject(LayerStore);

  readonly modes: SimulationMode[] = ['1d', '2d', '1d2d'];
  readonly selectedMode = signal<SimulationMode>('2d');
  readonly steps        = signal(500);
  readonly stepN        = signal(10);
  readonly errorMsg     = signal('');

  private subs: Subscription[] = [];

  ngOnInit(): void {
    const wsUrl = `ws://${location.host}/ws`;
    this.ws.connect(wsUrl);
    this.store.setWsConnected(true);

    const sub = this.ws.messages$.pipe(
      filter(m => ['running', 'complete', 'error'].includes(m['type'] as string)),
    ).subscribe(msg => {
      if (msg['type'] === 'running') {
        this.store.updateFromStep(msg['elapsed_time'] as number, msg['step'] as number, null);
      } else if (msg['type'] === 'complete') {
        this.store.setStatus('idle');
      } else if (msg['type'] === 'error') {
        this.store.setError(msg['message'] as string);
      }
    });
    this.subs.push(sub);
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
  }

  start(): void {
    this.errorMsg.set('');
    this.api.startSimulation({ mode: this.selectedMode(), steps: this.steps() }).subscribe({
      next: res => {
        this.store.setMode(res.mode as SimulationMode);
        this.store.setStatus('idle');
        // Auto-create sim layers in the layer store
        this._ensureSimLayers();
      },
      error: err => this.errorMsg.set(err.error?.detail ?? 'Failed to start'),
    });
  }

  step(): void {
    this.api.step(this.stepN()).subscribe({
      next: state => {
        this.store.updateFromStep(state.elapsed_time, state.current_step,
          state.stats ? {
            maxDepth: state.stats.max_depth, meanDepth: state.stats.mean_depth,
            floodedCells: state.stats.flooded_cells, floodedAreaKm2: state.stats.flooded_area_km2,
            dominantRisk: state.stats.dominant_risk as any,
          } : null,
        );
      },
      error: err => this.errorMsg.set(err.error?.detail ?? 'Step failed'),
    });
  }

  run(): void {
    if (!this.ws.connected) { this.errorMsg.set('WebSocket not connected'); return; }
    this.store.setStatus('running');
    this.ws.send({ type: 'run', steps: this.steps(), yield_every: 10 });
  }

  reset(): void {
    this.api.reset().subscribe({
      next:  () => this.store.resetState(),
      error: err => this.errorMsg.set(err.error?.detail ?? 'Reset failed'),
    });
  }

  private _ensureSimLayers(): void {
    const mode = this.selectedMode();
    if (mode === '2d' || mode === '1d2d') {
      this.layers.upsertLocalLayer({
        id: 'sim_flood_depth', name: 'Flood Depth', type: 'flood_depth',
        visibility: true, opacity: 0.8, z_index: 10,
        data_ref: 'sim:flood_depth',
        style: { color: '#38bdf8', colormap: 'blues', range_min: null, range_max: null, line_width: 1.5, point_size: 4 },
        metadata: { crs_epsg: null, bounds: null, resolution: null, feature_count: null, source_filename: null },
      });
      this.layers.upsertLocalLayer({
        id: 'sim_flood_risk', name: 'Flood Risk', type: 'flood_risk',
        visibility: false, opacity: 0.75, z_index: 11,
        data_ref: 'sim:flood_risk',
        style: { color: '#ef4444', colormap: 'risk', range_min: 0, range_max: 4, line_width: 1.5, point_size: 4 },
        metadata: { crs_epsg: null, bounds: null, resolution: null, feature_count: null, source_filename: null },
      });
    }
  }
}
