import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface GeoJSONGeometry {
  type: string;
  coordinates: any;
}
export interface GeoJSONFeature {
  type: 'Feature';
  geometry: GeoJSONGeometry;
  properties: Record<string, any> | null;
}
export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}
export interface VectorGeoJSONResponse {
  file_id:  string;
  filename: string;
  crs_epsg: number | null;
  bounds:   { min_x: number; min_y: number; max_x: number; max_y: number };
  geojson:  GeoJSONFeatureCollection;
}

export interface LayerStyle {
  color:      string;
  colormap:   string;
  range_min:  number | null;
  range_max:  number | null;
  line_width: number;
  point_size: number;
}

export interface LayerMetadata {
  crs_epsg:        number | null;
  bounds:          { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  resolution:      number[] | null;
  feature_count:   number | null;
  source_filename: string | null;
}

export type LayerType = 'dem' | 'flood_depth' | 'flood_risk' | 'vector' | 'rain' | 'channel' | 'building';

export interface Layer {
  id:         string;
  name:       string;
  type:       LayerType;
  visibility: boolean;
  opacity:    number;
  z_index:    number;
  style:      LayerStyle;
  data_ref:   string;
  metadata:   LayerMetadata;
}

export interface LayerCreate {
  name:       string;
  type:       LayerType;
  data_ref:   string;
  visibility?: boolean;
  opacity?:    number;
  z_index?:    number;
  style?:      Partial<LayerStyle>;
  metadata?:   Partial<LayerMetadata>;
}

export interface LayerUpdate {
  name?:       string;
  visibility?: boolean;
  opacity?:    number;
  z_index?:    number;
  style?:      Partial<LayerStyle>;
}

@Injectable({ providedIn: 'root' })
export class LayerApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/layers';

  getLayers(): Observable<{ layers: Layer[]; count: number }> {
    return this.http.get<{ layers: Layer[]; count: number }>(this.base);
  }

  createLayer(req: LayerCreate): Observable<Layer> {
    return this.http.post<Layer>(this.base, req);
  }

  updateLayer(id: string, patch: LayerUpdate): Observable<Layer> {
    return this.http.patch<Layer>(`${this.base}/${id}`, patch);
  }

  deleteLayer(id: string): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(`${this.base}/${id}`);
  }

  reorderLayers(orderedIds: string[]): Observable<{ layers: Layer[]; count: number }> {
    return this.http.post<{ layers: Layer[]; count: number }>(`${this.base}/reorder`, { ordered_ids: orderedIds });
  }

  uploadGisFile(file: File, targetCrs?: number): Observable<{
    file_id:         string;
    filename:        string;
    type:            string;         // 'raster' | 'vector'
    format:          string;
    // raster-only
    bounds?:         { min_x: number; min_y: number; max_x: number; max_y: number };
    dimensions?:     { width: number; height: number };
    elevation_stats?: { min: number; max: number; mean: number; std: number };
    // vector-only
    feature_count?:  number;
    geometry_types?: string[];
    crs?:            number | null;
    attributes?:     string[];
  }> {
    const fd = new FormData();
    fd.append('file', file);
    if (targetCrs != null) fd.append('target_crs', String(targetCrs));
    return this.http.post<any>('/api/gis/upload', fd);
  }

  getVectorGeoJSON(fileId: string): Observable<VectorGeoJSONResponse> {
    return this.http.get<VectorGeoJSONResponse>(`/api/gis/vector/${fileId}`);
  }

  getBuildingsGeoJSON(fileId: string): Observable<VectorGeoJSONResponse> {
    return this.http.get<VectorGeoJSONResponse>(`/api/gis/buildings/${fileId}`);
  }
}
