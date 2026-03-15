/**
 * TerrainViewer — thin canvas host.
 *
 * The service is provided by MapPage so MapPage can call rendering methods.
 * This component is just responsible for owning the <canvas> element.
 */
import { Component, ElementRef, OnDestroy, OnInit, ViewChild, inject } from '@angular/core';
import { TerrainViewerService } from './terrain-viewer.service';

export { TerrainViewerService };

@Component({
  selector: 'app-terrain-viewer',
  standalone: true,
  template: `<canvas #canvas class="canvas"></canvas>`,
  styles: [`
    :host  { display: block; position: absolute; inset: 0; }
    .canvas { width: 100%; height: 100%; display: block; cursor: grab; }
    .canvas:active { cursor: grabbing; }
  `],
})
export class TerrainViewer implements OnInit, OnDestroy {
  @ViewChild('canvas', { static: true })
  private readonly canvasRef!: ElementRef<HTMLCanvasElement>;

  private readonly svc = inject(TerrainViewerService);

  ngOnInit():    void { this.svc.init(this.canvasRef.nativeElement); }
  ngOnDestroy(): void { this.svc.destroy(); }
}
