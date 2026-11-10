import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/academies/academy-list/academy-list').then(m => m.AcademyListPage),
  },
  {
    path: 'academias/:slug',
    loadComponent: () =>
      import('./features/academies/academy-detail/academy-detail').then(m => m.AcademyDetailPage),
  },
  { path: '**', redirectTo: '' },
];
