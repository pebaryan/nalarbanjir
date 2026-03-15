import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PickEvent } from '../terrain-viewer/terrain-viewer.service';

@Component({
  selector: 'app-inspector-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="inspector">
      <div class="inspector__header">
        <span>Inspector</span>
        <button class="close-btn" (click)="close.emit()">✕</button>
      </div>
      <div class="inspector__grid">
        <span class="lbl">Grid</span>
        <span class="val">({{ event().gridI }}, {{ event().gridJ }})</span>
        <span class="lbl">World X</span>
        <span class="val">{{ event().worldX | number:'1.1-1' }} m</span>
        <span class="lbl">World Z</span>
        <span class="val">{{ event().worldZ | number:'1.1-1' }} m</span>
        <span class="lbl">Elevation</span>
        <span class="val">{{ event().elevation | number:'1.2-2' }} m</span>
        <span class="lbl">Layer</span>
        <span class="val layer-id">{{ event().layerId }}</span>
      </div>
    </div>
  `,
  styles: [`
    .inspector {
      background: rgba(15,23,42,0.95);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(56,189,248,0.3);
      border-radius: 8px;
      min-width: 200px;
      font-size: 0.78rem;
      color: #e2e8f0;
      overflow: hidden;
    }
    .inspector__header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.4rem 0.6rem;
      border-bottom: 1px solid rgba(51,65,85,0.5);
      color: #38bdf8; font-weight: 600; font-size: 0.75rem;
    }
    .close-btn { background:none; border:none; color:#475569; cursor:pointer; font-size:0.75rem; &:hover{color:#ef4444;} }
    .inspector__grid {
      display: grid; grid-template-columns: auto 1fr;
      gap: 0.25rem 0.75rem; padding: 0.5rem 0.6rem;
    }
    .lbl { color: #475569; }
    .val { color: #e2e8f0; font-variant-numeric: tabular-nums; }
    .layer-id { font-size: 0.68rem; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 120px; }
  `],
})
export class InspectorPanel {
  readonly event = input.required<PickEvent>();
  readonly close = output<void>();
}
