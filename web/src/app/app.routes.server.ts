import { HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { RenderMode, ServerRoute } from '@angular/ssr';
import { firstValueFrom } from 'rxjs';

import { API_BASE_URL } from './core/api-base-url';

export const serverRoutes: ServerRoute[] = [
  {
    path: '',
    renderMode: RenderMode.Prerender,
  },
  {
    path: 'acerca',
    renderMode: RenderMode.Prerender,
  },
  {
    path: 'academias/:slug',
    renderMode: RenderMode.Prerender,
    async getPrerenderParams() {
      const http = inject(HttpClient);
      const base = inject(API_BASE_URL).replace(/\/$/, '');
      const slugs: string[] = [];
      let page = 1;
      let total = Number.POSITIVE_INFINITY;

      while (slugs.length < total) {
        const response = await firstValueFrom(
          http.get<{ items: { slug: string }[]; total: number }>(`${base}/academies`, {
            params: { page, page_size: 100 },
          }),
        );
        total = response.total;
        slugs.push(...response.items.map(item => item.slug));
        if (response.items.length === 0) {
          break;
        }
        page += 1;
      }

      return slugs.map(slug => ({ slug }));
    },
  },
  {
    path: '**',
    renderMode: RenderMode.Client,
  },
];
