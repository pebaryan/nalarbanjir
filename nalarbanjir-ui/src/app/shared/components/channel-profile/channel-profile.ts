/**
 * ChannelProfile
 *
 * Renders a longitudinal profile of a 1D channel reach as an inline SVG:
 *   - Bed elevation (brown fill)
 *   - Water surface elevation (blue line)
 *   - Discharge axis on the right (optional)
 */
import { Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface ChannelProfileData {
  chainage: number[];            // [m] along reach
  bedElev: number[];             // [m a.s.l.] bed elevation at each node
  waterSurfaceElev: number[];    // [m a.s.l.] water surface at each node
  discharge: number[];           // [m³/s]
}

@Component({
  selector: 'app-channel-profile',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (data(); as d) {
      <div class="profile">
        <svg [attr.viewBox]="viewBox()" preserveAspectRatio="none" class="profile__svg">
          <!-- Bed area -->
          <polygon [attr.points]="bedPolygon()" class="bed-fill" />
          <!-- Bed line -->
          <polyline [attr.points]="bedLine()" class="bed-line" />
          <!-- Water surface -->
          <polyline [attr.points]="waterLine()" class="water-line" />
        </svg>
        <div class="profile__legend">
          <span class="legend-item legend-item--bed">Bed</span>
          <span class="legend-item legend-item--water">Water surface</span>
        </div>
      </div>
    } @else {
      <div class="profile profile--empty">No 1D channel data</div>
    }
  `,
  styles: [`
    .profile {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 1rem;
      height: 200px;
      display: flex;
      flex-direction: column;

      &--empty {
        align-items: center;
        justify-content: center;
        color: #475569;
        font-size: 0.9rem;
      }
    }
    .profile__svg {
      flex: 1;
      width: 100%;
      overflow: visible;
    }
    .bed-fill   { fill: #78350f; fill-opacity: 0.6; }
    .bed-line   { fill: none; stroke: #b45309; stroke-width: 1.5; }
    .water-line { fill: none; stroke: #38bdf8; stroke-width: 2; }
    .profile__legend {
      display: flex; gap: 1rem; margin-top: 4px;
      font-size: 0.72rem;
    }
    .legend-item {
      display: flex; align-items: center; gap: 4px;
      &::before { content: ''; display: inline-block; width: 20px; height: 3px; border-radius: 2px; }
      &--bed::before   { background: #b45309; }
      &--water::before { background: #38bdf8; }
      color: #94a3b8;
    }
  `],
})
export class ChannelProfile {
  readonly data = input<ChannelProfileData | null>(null);

  // ── SVG helpers ──────────────────────────────────────────────────────

  private readonly _svgW = 1000;
  private readonly _svgH = 200;
  private readonly _pad  = 10;

  viewBox = computed(() => `0 0 ${this._svgW} ${this._svgH}`);

  bedLine = computed(() => this._polyPoints(d => d.bedElev));
  waterLine = computed(() => this._polyPoints(d => d.waterSurfaceElev));

  bedPolygon = computed(() => {
    const d = this.data();
    if (!d) return '';
    const pts = this._polyPoints(_ => _.bedElev);
    const ch  = d.chainage;
    const xMin = this._xScale(ch[0], ch);
    const xMax = this._xScale(ch[ch.length - 1], ch);
    return `${pts} ${xMax},${this._svgH} ${xMin},${this._svgH}`;
  });

  private _yRange = computed(() => {
    const d = this.data();
    if (!d) return { min: 0, max: 10 };
    const all = [...d.bedElev, ...d.waterSurfaceElev];
    return { min: Math.min(...all), max: Math.max(...all) };
  });

  private _xScale(x: number, arr: number[]): number {
    const min = arr[0], max = arr[arr.length - 1];
    if (max === min) return this._pad;
    return this._pad + ((x - min) / (max - min)) * (this._svgW - 2 * this._pad);
  }

  private _yScale(y: number): number {
    const { min, max } = this._yRange();
    const range = max - min || 1;
    // SVG y-axis is inverted: high values = small y
    return this._svgH - this._pad - ((y - min) / range) * (this._svgH - 2 * this._pad);
  }

  private _polyPoints(selector: (d: ChannelProfileData) => number[]): string {
    const d = this.data();
    if (!d) return '';
    return d.chainage
      .map((x, i) => `${this._xScale(x, d.chainage)},${this._yScale(selector(d)[i])}`)
      .join(' ');
  }
}
