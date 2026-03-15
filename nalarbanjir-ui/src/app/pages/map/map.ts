import { Component, inject, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { ApiService } from '../../core/services/api.service';
import { SimulationStore } from '../../core/store/simulation.store';
import { TerrainViewer, TerrainData, WaterData } from '../../shared/components/terrain-viewer/terrain-viewer';
import { ChannelProfile, ChannelProfileData } from '../../shared/components/channel-profile/channel-profile';
import { AnalyticsPanel, AnalyticsSnapshot } from '../../shared/components/analytics-panel/analytics-panel';

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule, TerrainViewer, ChannelProfile, AnalyticsPanel],
  templateUrl: './map.html',
  styleUrl: './map.scss',
})
export class MapPage implements OnInit, OnDestroy {
  private readonly api   = inject(ApiService);
  readonly store         = inject(SimulationStore);

  readonly terrain   = signal<TerrainData | null>(null);
  readonly water     = signal<WaterData | null>(null);
  readonly profile   = signal<ChannelProfileData | null>(null);
  readonly analytics = signal<AnalyticsSnapshot[]>([]);

  private subs: Subscription[] = [];

  ngOnInit(): void {
    // Load terrain mesh once
    this.api.getTerrainMesh().subscribe(mesh => {
      this.terrain.set({
        elevation: mesh.elevation,
        nx: mesh.nx, ny: mesh.ny,
        dx: mesh.dx, dy: mesh.dy,
      });
    });

    // Poll simulation state every 2 seconds to update water surface
    const poll = interval(2000).pipe(
      switchMap(() => this.api.getState()),
    ).subscribe({
      next: state => {
        if (state.state_2d) {
          const s2d = state.state_2d;
          const t = this.terrain();
          this.water.set({
            depth: s2d.water_depth,
            bedElev: null,
            nx: s2d.water_depth.length,
            ny: s2d.water_depth[0]?.length ?? 0,
            dx: t?.dx ?? 100,
            dy: t?.dy ?? 100,
          });

          if (state.stats) {
            this.analytics.update(hist => {
              const snap: AnalyticsSnapshot = {
                time: state.elapsed_time,
                maxDepth: state.stats!.max_depth,
                floodedArea: state.stats!.flooded_area_km2,
              };
              return [...hist.slice(-99), snap];   // keep last 100 snapshots
            });
          }
        }

        if (state.state_1d) {
          const s1d = state.state_1d;
          this.profile.set({
            chainage: s1d.chainage,
            bedElev: s1d.water_surface_elev.map((h, i) =>
              h - (s1d.discharge[i] > 0 ? 1 : 0)  // approximate bed
            ),
            waterSurfaceElev: s1d.water_surface_elev,
            discharge: s1d.discharge,
          });
        }
      },
      error: () => {},   // engine may not be started — ignore
    });
    this.subs.push(poll);
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
  }
}
