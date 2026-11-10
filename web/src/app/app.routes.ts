import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/academies/academy-list/academy-list').then(m => m.AcademyListPage),
  },
  { path: '**', redirectTo: '' },
];
