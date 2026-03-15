import {
  Component, ElementRef, OnDestroy, OnInit, ViewChild,
  inject, input, effect,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TerrainViewerService } from './terrain-viewer.service';

export interface TerrainData {
  elevation: number[][];
  nx: number; ny: number; dx: number; dy: number;
}

export interface WaterData {
  depth: number[][];
  bedElev: number[][] | null;
  nx: number; ny: number; dx: number; dy: number;
}

@Component({
  selector: 'app-terrain-viewer',
  standalone: true,
  imports: [CommonModule],
  providers: [TerrainViewerService],   // scoped instance per component
  template: `
    <canvas #canvas class="viewer-canvas"></canvas>
    @if (!ready()) {
      <div class="viewer-overlay">Loading terrain…</div>
    }
  `,
  styles: [`
    :host { display: block; position: relative; width: 100%; height: 100%; }
    .viewer-canvas { width: 100%; height: 100%; display: block; }
    .viewer-overlay {
      position: absolute; inset: 0;
      display: flex; align-items: center; justify-content: center;
      color: #475569; font-size: 1rem;
      background: #0f172a;
    }
  `],
})
export class TerrainViewer implements OnInit, OnDestroy {
  @ViewChild('canvas', { static: true })
  private readonly canvasRef!: ElementRef<HTMLCanvasElement>;

  readonly terrain = input<TerrainData | null>(null);
  readonly water   = input<WaterData | null>(null);

  private readonly svc = inject(TerrainViewerService);
  protected ready = () => this.terrain() !== null;

  constructor() {
    // Reactively upload terrain whenever the input changes
    effect(() => {
      const t = this.terrain();
      if (t) {
        this.svc.updateTerrain(t.elevation, t.nx, t.ny, t.dx, t.dy);
      }
    });

    effect(() => {
      const w = this.water();
      if (w) {
        this.svc.updateWater(w.depth, w.bedElev, w.nx, w.ny, w.dx, w.dy);
      }
    });
  }

  ngOnInit(): void {
    this.svc.init(this.canvasRef.nativeElement);
  }

  ngOnDestroy(): void {
    this.svc.destroy();
  }
}
