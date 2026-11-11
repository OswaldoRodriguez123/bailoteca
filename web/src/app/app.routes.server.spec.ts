import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { RenderMode } from '@angular/ssr';

import { API_BASE_URL } from './core/api-base-url';
import { serverRoutes } from './app.routes.server';

describe('serverRoutes', () => {
  it('prerenderiza la portada', () => {
    expect(serverRoutes).toContainEqual(
      expect.objectContaining({ path: '', renderMode: RenderMode.Prerender }),
    );
  });

  it('prerenderiza la página Acerca de', () => {
    expect(serverRoutes).toContainEqual(
      expect.objectContaining({ path: 'acerca', renderMode: RenderMode.Prerender }),
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

describe('getPrerenderParams', () => {
  let http: HttpTestingController;
  let params: () => Promise<Record<string, string>[]>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: 'https://api.test' },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const detail = serverRoutes.find(route => route.path === 'academias/:slug');
    params = (detail as { getPrerenderParams: typeof params }).getPrerenderParams;
  });

  afterEach(() => http.verify());

  it('devuelve un slug por academia', async () => {
    const promise = TestBed.runInInjectionContext(() => params());

    http
      .expectOne(request => request.url === 'https://api.test/academies')
      .flush({ items: [{ slug: 'a' }, { slug: 'b' }], total: 2, page: 1, page_size: 100 });

    await expect(promise).resolves.toEqual([{ slug: 'a' }, { slug: 'b' }]);
  });

  it('pagina cuando hay más de 100 academias', async () => {
    const promise = TestBed.runInInjectionContext(() => params());

    http.expectOne(request => request.params.get('page') === '1').flush({
      items: Array.from({ length: 100 }, (_, index) => ({ slug: `a${index}` })),
      total: 150,
      page: 1,
      page_size: 100,
    });
    await new Promise(resolve => setTimeout(resolve, 0));
    http.expectOne(request => request.params.get('page') === '2').flush({
      items: Array.from({ length: 50 }, (_, index) => ({ slug: `b${index}` })),
      total: 150,
      page: 2,
      page_size: 100,
    });

    await expect(promise).resolves.toHaveLength(150);
  });
});
