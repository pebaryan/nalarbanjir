import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export type SimulationMode = '1d' | '2d' | '1d2d';

export interface RunRequest {
  mode: SimulationMode;
  steps: number;
  broadcast_interval?: number;
  dem_file_id?: string;
  rainfall?: {
    pattern:   'uniform' | 'storm_cell' | 'frontal';
    intensity: number;
    duration:  number;
    storm_x?:  number;
    storm_y?:  number;
  };
}

export interface SimulationState {
  mode: SimulationMode;
  status: string;
  current_step: number;
  elapsed_time: number;
  state_2d?: {
    water_depth: number[][];
    velocity_x: number[][];
    velocity_y: number[][];
    flood_risk: number[][];
  };
  state_1d?: {
    chainage: number[];
    discharge: number[];
    water_surface_elev: number[];
    velocity: number[];
    node_ids: string[];
  };
  stats?: {
    max_depth: number;
    mean_depth: number;
    flooded_cells: number;
    flooded_area_km2: number;
    dominant_risk: string;
  };
}

export interface SimulationStatus {
  status: string;
  current_step: number;
  total_steps: number;
  elapsed_time: number;
}

export interface TerrainInfo {
  nx: number;
  ny: number;
  dx: number;
  dy: number;
  min_elevation: number;
  max_elevation: number;
  source: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  // ── Simulation ───────────────────────────────────────────────────────────

  startSimulation(req: RunRequest): Observable<{ ok: boolean; mode: string; message: string }> {
    return this.http.post<{ ok: boolean; mode: string; message: string }>(
      `${this.baseUrl}/simulation/start`,
      req,
    );
  }

  getStatus(): Observable<SimulationStatus> {
    return this.http.get<SimulationStatus>(`${this.baseUrl}/simulation/status`);
  }

  step(n = 1): Observable<SimulationState> {
    const params = new HttpParams().set('n', n.toString());
    return this.http.post<SimulationState>(`${this.baseUrl}/simulation/step`, null, { params });
  }

  getState(): Observable<SimulationState> {
    return this.http.get<SimulationState>(`${this.baseUrl}/simulation/state`);
  }

  reset(): Observable<{ ok: boolean; message: string }> {
    return this.http.post<{ ok: boolean; message: string }>(
      `${this.baseUrl}/simulation/reset`,
      null,
    );
  }

  // ── Terrain ──────────────────────────────────────────────────────────────

  getTerrainInfo(): Observable<TerrainInfo> {
    return this.http.get<TerrainInfo>(`${this.baseUrl}/terrain/info`);
  }

  getTerrainMesh(): Observable<{ nx: number; ny: number; dx: number; dy: number; elevation: number[][] }> {
    return this.http.get<{ nx: number; ny: number; dx: number; dy: number; elevation: number[][] }>(
      `${this.baseUrl}/terrain/mesh`,
    );
  }

  // ── Prediction ───────────────────────────────────────────────────────────

  getRiskGrid(): Observable<{ nx: number; ny: number; risk_grid: number[][]; summary: Record<string, number> }> {
    return this.http.get<{ nx: number; ny: number; risk_grid: number[][]; summary: Record<string, number> }>(
      `${this.baseUrl}/prediction/risk`,
    );
  }
}
