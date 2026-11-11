import { RenderMode } from '@angular/ssr';

import { serverRoutes } from './app.routes.server';

describe('serverRoutes', () => {
  it('prerenderiza la portada', () => {
    expect(serverRoutes).toContainEqual(
      expect.objectContaining({ path: '', renderMode: RenderMode.Prerender }),
    );
  });

  it('prerenderiza el detalle con un slug por academia', () => {
    const detail = serverRoutes.find(route => route.path === 'academias/:slug');

    expect(detail?.renderMode).toBe(RenderMode.Prerender);
    expect(detail && 'getPrerenderParams' in detail).toBe(true);
  });

  it('deja el catch-all a render en cliente', () => {
    expect(serverRoutes).toContainEqual(
      expect.objectContaining({ path: '**', renderMode: RenderMode.Client }),
    );
  });
});
