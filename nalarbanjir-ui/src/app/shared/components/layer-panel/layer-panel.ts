import { Component, inject, signal, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LayerStore } from '../../../core/store/layer.store';
import { LayerApiService, Layer } from '../../../core/services/layer-api.service';
import { COLORMAPS } from '../../utils/colormap';

@Component({
  selector: 'app-layer-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './layer-panel.html',
  styleUrl:    './layer-panel.scss',
})
export class LayerPanel {
  readonly store      = inject(LayerStore);
  private readonly api = inject(LayerApiService);

  readonly colormaps  = COLORMAPS;
  readonly uploading  = signal(false);
  readonly uploadErr  = signal('');

  // Drag-to-reorder
  private dragId = '';

  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  // ── Visibility / opacity ───────────────────────────────────────────────

  toggleVisibility(layer: Layer): void {
    this.store.updateLayer(layer.id, { visibility: !layer.visibility });
  }

  setOpacity(layer: Layer, value: number): void {
    this.store.updateLayer(layer.id, { opacity: value });
  }

  // ── Selection / config ─────────────────────────────────────────────────

  toggleSelect(id: string): void {
    this.store.selectLayer(this.store.selectedLayerId() === id ? null : id);
  }

  updateStyle(layer: Layer, field: string, value: string | number | null): void {
    this.store.updateLayer(layer.id, { style: { ...layer.style, [field]: value } });
  }

  // ── Delete ─────────────────────────────────────────────────────────────

  remove(layer: Layer, e: Event): void {
    e.stopPropagation();
    this.store.removeLayer(layer.id);
  }

  // ── Upload GIS file → create DEM layer ────────────────────────────────

  openFilePicker(): void { this.fileInput.nativeElement.click(); }

  onFileSelected(e: Event): void {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;

    this.uploading.set(true);
    this.uploadErr.set('');

    this.api.uploadGisFile(file).subscribe({
      next: res => {
        const baseName = file.name.replace(/\.[^.]+$/, '');

        if (res.type === 'building') {
          this.store.addLayer({
            name:     baseName,
            type:     'building',
            data_ref: res.file_id,
            style:    { color: '#d4a96a', colormap: 'terrain', range_min: null, range_max: null, line_width: 1.5, point_size: 4 },
            metadata: {
              source_filename: res.filename,
              bounds:          res.bounds ?? null,
              crs_epsg:        res.crs ?? null,
              resolution:      null,
              feature_count:   res.feature_count ?? null,
            },
          });
        } else if (res.type === 'vector') {
          // Decide layer type from geometry: lines → channel, polygons → vector
          const geomTypes: string[] = res.geometry_types ?? [];
          const isLineGeom = geomTypes.some(g => g.toLowerCase().includes('line'));
          const layerType = isLineGeom ? 'channel' : 'vector';

          this.store.addLayer({
            name:     baseName,
            type:     layerType,
            data_ref: res.file_id,
            style:    { color: '#38bdf8', colormap: 'blues', range_min: null, range_max: null, line_width: 2, point_size: 4 },
            metadata: {
              source_filename: res.filename,
              bounds:          res.bounds ?? null,
              crs_epsg:        res.crs ?? null,
              resolution:      null,
              feature_count:   res.feature_count ?? null,
            },
          });
        } else {
          this.store.addLayer({
            name:     baseName,
            type:     'dem',
            data_ref: res.file_id,
            style:    { color: '#74c69d', colormap: 'terrain', range_min: res.elevation_stats?.min ?? null, range_max: res.elevation_stats?.max ?? null, line_width: 1.5, point_size: 4 },
            metadata: {
              source_filename: res.filename,
              bounds:          res.bounds ?? null,
              crs_epsg:        null, resolution: null, feature_count: null,
            },
          });
        }

        this.uploading.set(false);
        this.fileInput.nativeElement.value = '';
      },
      error: err => {
        this.uploadErr.set(err.error?.detail ?? 'Upload failed');
        this.uploading.set(false);
      },
    });
  }

  // ── Drag-to-reorder ────────────────────────────────────────────────────

  onDragStart(id: string): void { this.dragId = id; }

  onDragOver(e: DragEvent): void { e.preventDefault(); }

  onDrop(targetId: string): void {
    if (!this.dragId || this.dragId === targetId) return;
    const ids     = this.store.orderedLayers().map(l => l.id);
    const fromIdx = ids.indexOf(this.dragId);
    const toIdx   = ids.indexOf(targetId);
    ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, this.dragId);
    // orderedLayers is high→low z_index, so reverse for API (API wants bottom→top)
    this.store.reorderLayers([...ids].reverse());
    this.dragId = '';
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  readonly layerTypeIcon: Record<string, string> = {
    dem:         '⛰',
    flood_depth: '💧',
    flood_risk:  '⚠',
    vector:      '🗺',
    rain:        '🌧',
    channel:     '〰',
    building:    '🏢',
  };

  trackById(_: number, l: Layer): string { return l.id; }
}
