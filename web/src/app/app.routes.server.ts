import { RenderMode, ServerRoute } from '@angular/ssr';

export const serverRoutes: ServerRoute[] = [
  {
    path: '',
    renderMode: RenderMode.Prerender,
  },
  {
    path: 'academias/:slug',
    renderMode: RenderMode.Prerender,
    async getPrerenderParams() {
      return [];
    },
  },
  {
    path: '**',
    renderMode: RenderMode.Client,
  },
];
