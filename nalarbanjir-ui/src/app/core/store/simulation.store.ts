import { computed } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import type { SimulationMode } from '../services/api.service';

export type SimulationStatus = 'idle' | 'running' | 'paused' | 'error';
export type RiskLevel = 'none' | 'minor' | 'moderate' | 'major' | 'severe';

interface FloodStats {
  maxDepth: number;
  meanDepth: number;
  floodedCells: number;
  floodedAreaKm2: number;
  dominantRisk: RiskLevel;
}

interface SimulationState {
  mode: SimulationMode;
  status: SimulationStatus;
  currentTime: number;
  stepCount: number;
  isWsConnected: boolean;
  stats: FloodStats | null;
  errorMessage: string | null;
  /** Incremented each time the engine is freshly initialized (⚙ Initialize clicked). */
  initCount: number;
}

const initialState: SimulationState = {
  mode: '2d',
  status: 'idle',
  currentTime: 0,
  stepCount: 0,
  isWsConnected: false,
  stats: null,
  errorMessage: null,
  initCount: 0,
};

export const SimulationStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withComputed(state => ({
    formattedTime: computed(() => `${state.currentTime().toFixed(1)} s`),
    formattedStep: computed(() => `Step ${state.stepCount()}`),
    isRunning: computed(() => state.status() === 'running'),
    hasError: computed(() => state.status() === 'error'),
    floodedAreaStr: computed(() => {
      const s = state.stats();
      return s ? `${s.floodedAreaKm2.toFixed(2)} km²` : '—';
    }),
    maxDepthStr: computed(() => {
      const s = state.stats();
      return s ? `${s.maxDepth.toFixed(2)} m` : '—';
    }),
  })),
  withMethods(store => ({
    setMode(mode: SimulationMode): void {
      patchState(store, { mode });
    },
    setStatus(status: SimulationStatus): void {
      patchState(store, { status });
    },
    updateFromStep(time: number, step: number, stats: FloodStats | null): void {
      patchState(store, { currentTime: time, stepCount: step, stats });
    },
    setWsConnected(connected: boolean): void {
      patchState(store, { isWsConnected: connected });
    },
    setError(message: string): void {
      patchState(store, { status: 'error', errorMessage: message });
    },
    resetState(): void {
      patchState(store, { ...initialState });
    },
    markInitialized(): void {
      patchState(store, { initCount: store.initCount() + 1 });
    },
  })),
);
