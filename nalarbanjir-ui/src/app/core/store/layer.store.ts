import { computed, inject } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { LayerApiService, Layer, LayerCreate, LayerUpdate } from '../services/layer-api.service';

interface LayerState {
  layers:          Layer[];
  selectedLayerId: string | null;
  loading:         boolean;
  error:           string | null;
}

const initialState: LayerState = {
  layers:          [],
  selectedLayerId: null,
  loading:         false,
  error:           null,
};

export const LayerStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),

  withComputed(state => ({
    // sorted bottom→top (high z_index = top layer)
    orderedLayers: computed(() =>
      [...state.layers()].sort((a, b) => b.z_index - a.z_index),
    ),
    visibleLayers: computed(() =>
      state.layers().filter(l => l.visibility),
    ),
    selectedLayer: computed(() =>
      state.layers().find(l => l.id === state.selectedLayerId()) ?? null,
    ),
    demLayers: computed(() =>
      state.layers().filter(l => l.type === 'dem'),
    ),
    floodDepthLayer: computed(() =>
      state.layers().find(l => l.type === 'flood_depth' && l.visibility) ?? null,
    ),
    floodRiskLayer: computed(() =>
      state.layers().find(l => l.type === 'flood_risk' && l.visibility) ?? null,
    ),
  })),

  withMethods((store, api = inject(LayerApiService)) => ({

    loadLayers(): void {
      patchState(store, { loading: true });
      api.getLayers().subscribe({
        next:  res => patchState(store, { layers: res.layers, loading: false }),
        error: err => patchState(store, { error: err.message, loading: false }),
      });
    },

    addLayer(req: LayerCreate): void {
      api.createLayer(req).subscribe({
        next:  layer => patchState(store, { layers: [...store.layers(), layer] }),
        error: err   => patchState(store, { error: err.message }),
      });
    },

    /** Optimistic update, then confirm from server. 404 = local-only layer, silently accepted. */
    updateLayer(id: string, patch: LayerUpdate): void {
      patchState(store, {
        layers: store.layers().map(l => l.id === id ? { ...l, ...patch, style: patch.style ? { ...l.style, ...patch.style } : l.style } : l),
      });
      api.updateLayer(id, patch).subscribe({
        next:  updated => patchState(store, { layers: store.layers().map(l => l.id === id ? updated : l) }),
        error: () => {}, // 404 = layer not persisted to backend (e.g. auto sim layers) — keep local state
      });
    },

    removeLayer(id: string): void {
      // Optimistic removal — works for local-only layers (404 from API is fine)
      patchState(store, {
        layers:          store.layers().filter(l => l.id !== id),
        selectedLayerId: store.selectedLayerId() === id ? null : store.selectedLayerId(),
      });
      api.deleteLayer(id).subscribe({ error: () => {} });
    },

    reorderLayers(orderedIds: string[]): void {
      // Optimistic local reindex
      patchState(store, {
        layers: store.layers().map(l => ({ ...l, z_index: orderedIds.indexOf(l.id) })),
      });
      api.reorderLayers(orderedIds).subscribe();
    },

    selectLayer(id: string | null): void {
      patchState(store, { selectedLayerId: id });
    },

    /** Upsert a layer without hitting the API (for auto-created sim layers). */
    upsertLocalLayer(layer: Layer): void {
      const exists = store.layers().some(l => l.id === layer.id);
      if (exists) {
        patchState(store, { layers: store.layers().map(l => l.id === layer.id ? layer : l) });
      } else {
        patchState(store, { layers: [...store.layers(), layer] });
      }
    },

  })),
);
