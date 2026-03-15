import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/dashboard/dashboard').then(m => m.Dashboard),
    title: 'Dashboard — Nalarbanjir',
  },
  {
    path: 'simulation',
    loadComponent: () => import('./pages/simulation/simulation').then(m => m.SimulationPage),
    title: 'Simulation — Nalarbanjir',
  },
  {
    path: 'map',
    loadComponent: () => import('./pages/map/map').then(m => m.MapPage),
    title: 'Map — Nalarbanjir',
  },
  { path: '**', redirectTo: '' },
];
