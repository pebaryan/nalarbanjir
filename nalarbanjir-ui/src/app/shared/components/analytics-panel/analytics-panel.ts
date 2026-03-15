/**
 * AnalyticsPanel
 *
 * Displays a time-series sparkline of max flood depth and flooded area
 * using an inline SVG path.  Lightweight — no charting library required.
 */
import { Component, computed, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface AnalyticsSnapshot {
  time: number;       // simulation time [s]
  maxDepth: number;   // [m]
  floodedArea: number; // [km²]
}

@Component({
  selector: 'app-analytics-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="analytics">
      <h2>Flood Analytics</h2>

      @if (history().length === 0) {
        <p class="muted">Run a simulation to see analytics.</p>
      } @else {
        <div class="charts">
          <div class="chart">
            <span class="chart__label">Max Depth (m)</span>
            <svg viewBox="0 0 300 60" class="sparkline">
              <polyline [attr.points]="depthPath()" class="line line--depth" />
            </svg>
            <span class="chart__val">{{ latestDepth() | number:'1.2-2' }} m</span>
          </div>

          <div class="chart">
            <span class="chart__label">Flooded Area (km²)</span>
            <svg viewBox="0 0 300 60" class="sparkline">
              <polyline [attr.points]="areaPath()" class="line line--area" />
            </svg>
            <span class="chart__val">{{ latestArea() | number:'1.2-2' }} km²</span>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .analytics {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 1.25rem;
      h2 {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8;
        margin: 0 0 1rem;
      }
    }
    .muted { color: #475569; font-size: 0.9rem; }
    .charts { display: flex; gap: 1.5rem; flex-wrap: wrap; }
    .chart {
      flex: 1 1 200px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      &__label { font-size: 0.75rem; color: #64748b; }
      &__val   { font-size: 1rem; font-weight: 700; color: #e2e8f0; }
    }
    .sparkline { width: 100%; height: 60px; overflow: visible; }
    .line { fill: none; stroke-width: 2; stroke-linejoin: round; }
    .line--depth { stroke: #f97316; }
    .line--area  { stroke: #38bdf8; }
  `],
})
export class AnalyticsPanel {
  readonly history = input<AnalyticsSnapshot[]>([]);

  latestDepth = computed(() => {
    const h = this.history();
    return h.length ? h[h.length - 1].maxDepth : 0;
  });

  latestArea = computed(() => {
    const h = this.history();
    return h.length ? h[h.length - 1].floodedArea : 0;
  });

  depthPath = computed(() =>
    this._sparkline(this.history().map(s => s.maxDepth))
  );

  areaPath = computed(() =>
    this._sparkline(this.history().map(s => s.floodedArea))
  );

  private _sparkline(values: number[]): string {
    if (values.length < 2) return '';
    const W = 300, H = 60, pad = 4;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return values
      .map((v, i) => {
        const x = pad + (i / (values.length - 1)) * (W - 2 * pad);
        const y = H - pad - ((v - min) / range) * (H - 2 * pad);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }
}
