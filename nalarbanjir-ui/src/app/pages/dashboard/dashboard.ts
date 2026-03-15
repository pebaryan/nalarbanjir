import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { SimulationStore } from '../../core/store/simulation.store';
import { StatusBadge } from '../../shared/components/status-badge/status-badge';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule, StatusBadge],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private readonly api = inject(ApiService);
  readonly store = inject(SimulationStore);

  readonly terrainInfo = signal<{ nx: number; ny: number; dx: number; min_elevation: number; max_elevation: number } | null>(null);
  readonly loading = signal(true);

  ngOnInit(): void {
    this.api.getTerrainInfo().subscribe({
      next: info => {
        this.terrainInfo.set(info);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
