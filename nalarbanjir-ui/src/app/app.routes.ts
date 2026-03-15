import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/map/map').then(m => m.MapPage),
    title: 'Nalarbanjir — Flood Prediction',
  },
  { path: '**', redirectTo: '' },
];
