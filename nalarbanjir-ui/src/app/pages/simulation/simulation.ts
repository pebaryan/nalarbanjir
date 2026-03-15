import { Component, inject, signal, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { filter } from 'rxjs/operators';

import { ApiService, SimulationMode } from '../../core/services/api.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { SimulationStore } from '../../core/store/simulation.store';
import { StatusBadge } from '../../shared/components/status-badge/status-badge';

@Component({
  selector: 'app-simulation',
  standalone: true,
  imports: [CommonModule, FormsModule, StatusBadge],
  templateUrl: './simulation.html',
  styleUrl: './simulation.scss',
})
export class SimulationPage implements OnInit, OnDestroy {
  private readonly api    = inject(ApiService);
  private readonly ws     = inject(WebSocketService);
  readonly store          = inject(SimulationStore);

  selectedMode = signal<SimulationMode>('2d');
  steps        = signal(500);
  stepN        = signal(10);
  errorMsg     = signal('');

  private subs: Subscription[] = [];

  readonly modes: SimulationMode[] = ['1d', '2d', '1d2d'];

  // ── WebSocket lifecycle ──────────────────────────────────────────────────

  ngOnInit(): void {
    const wsUrl = `ws://${location.host}/ws`;
    this.ws.connect(wsUrl);
    this.store.setWsConnected(true);

    const sub = this.ws.messages$.pipe(
      filter(m => ['running', 'complete', 'error'].includes(m['type'] as string)),
    ).subscribe(msg => {
      if (msg['type'] === 'running') {
        this.store.updateFromStep(
          msg['elapsed_time'] as number,
          msg['step'] as number,
          null,
        );
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
    this.ws.disconnect();
    this.store.setWsConnected(false);
  }

  // ── Controls ─────────────────────────────────────────────────────────────

  start(): void {
    this.errorMsg.set('');
    this.api.startSimulation({
      mode: this.selectedMode(),
      steps: this.steps(),
    }).subscribe({
      next: res => {
        this.store.setMode(res.mode as SimulationMode);
        this.store.setStatus('idle');
      },
      error: err => this.errorMsg.set(err.error?.detail ?? 'Failed to start simulation'),
    });
  }

  stepN_times(): void {
    this.api.step(this.stepN()).subscribe({
      next: state => {
        this.store.updateFromStep(
          state.elapsed_time,
          state.current_step,
          state.stats ? {
            maxDepth: state.stats.max_depth,
            meanDepth: state.stats.mean_depth,
            floodedCells: state.stats.flooded_cells,
            floodedAreaKm2: state.stats.flooded_area_km2,
            dominantRisk: state.stats.dominant_risk as any,
          } : null,
        );
      },
      error: err => this.errorMsg.set(err.error?.detail ?? 'Step failed'),
    });
  }

  runViaWs(): void {
    if (!this.ws.connected) {
      this.errorMsg.set('WebSocket not connected');
      return;
    }
    this.store.setStatus('running');
    this.ws.send({ type: 'run', steps: this.steps(), yield_every: 10 });
  }

  reset(): void {
    this.api.reset().subscribe({
      next: () => this.store.resetState(),
      error: err => this.errorMsg.set(err.error?.detail ?? 'Reset failed'),
    });
  }
}
