/**
 * ProjectService — save and load complete project state as a JSON file.
 *
 * A project captures:
 *   - All layers (persisted + local-only sim layers)
 *   - Last simulation configuration (mode, steps, rainfall)
 *
 * Persisted layers (data_ref is a real file_id from /api/gis/upload) require
 * the file to still exist on the server. Local-only layers (data_ref starts
 * with "sim:") are restored entirely from the JSON.
 */
import { inject, Injectable } from '@angular/core';
import { LayerApiService, Layer, LayerCreate } from './layer-api.service';
import { LayerStore } from '../store/layer.store';

export interface ProjectSimConfig {
  mode:    '1d' | '2d' | '1d2d';
  steps:   number;
  rainfall: {
    pattern:   'uniform' | 'storm_cell' | 'frontal';
    intensity_mm_hr: number;
    duration_min:    number;
    storm_x?:  number;
    storm_y?:  number;
  };
}

export interface ProjectFile {
  version:     '1';
  name:        string;
  exported_at: string;  // ISO date string
  layers:      Layer[];
  simulation:  ProjectSimConfig;
}

@Injectable({ providedIn: 'root' })
export class ProjectService {
  private readonly layerApi = inject(LayerApiService);
  private readonly layerStore = inject(LayerStore);

  // ── Export ───────────────────────────────────────────────────────────────

  export(name: string, simConfig: ProjectSimConfig): void {
    const project: ProjectFile = {
      version:     '1',
      name,
      exported_at: new Date().toISOString(),
      layers:      this.layerStore.layers(),
      simulation:  simConfig,
    };

    const json = JSON.stringify(project, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href     = url;
    a.download = `${name.replace(/\s+/g, '_').toLowerCase()}.nalarbanjir.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Import ───────────────────────────────────────────────────────────────

  /**
   * Parse a project file and restore layers into the store.
   * Returns the simulation config from the file so the caller can apply it.
   */
  import(file: File): Promise<ProjectSimConfig> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const project = JSON.parse(reader.result as string) as ProjectFile;
          if (project.version !== '1') {
            reject(new Error(`Unknown project version: ${project.version}`));
            return;
          }
          this._restoreLayers(project.layers);
          resolve(project.simulation);
        } catch (e) {
          reject(e);
        }
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
  }

  // ── Internal ─────────────────────────────────────────────────────────────

  private _restoreLayers(layers: Layer[]): void {
    for (const layer of layers) {
      // Local-only layers (sim terrain, sim outputs) — restore directly to store
      if (layer.data_ref.startsWith('sim:')) {
        this.layerStore.upsertLocalLayer(layer);
        continue;
      }

      // Persistent layers — recreate in backend (no-op if server already has file)
      const req: LayerCreate = {
        name:       layer.name,
        type:       layer.type,
        data_ref:   layer.data_ref,
        visibility: layer.visibility,
        opacity:    layer.opacity,
        z_index:    layer.z_index,
        style:      layer.style,
        metadata:   layer.metadata,
      };
      this.layerApi.createLayer(req).subscribe({
        next:  created => this.layerStore.upsertLocalLayer(created),
        error: ()      => {
          // If backend rejects (file gone), still show layer locally so users know it existed
          this.layerStore.upsertLocalLayer(layer);
        },
      });
    }
  }
}
