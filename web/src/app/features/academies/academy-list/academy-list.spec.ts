import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { Observable, of, throwError } from 'rxjs';

import { routes } from '../../../app.routes';
import { AcademyQuery } from '../../../core/models/academy.models';
import { AcademiesApiService } from '../../../core/services/academies-api';
import { makeAcademy, makePage } from '../../../core/testing/academy.fixtures';
import { AcademyListPage } from './academy-list';

describe('AcademyListPage', () => {
  let harness: RouterTestingHarness;
  let componentInstance: AcademyListPage;
  let listAcademies: ReturnType<typeof vi.fn>;
  let listStyles: ReturnType<typeof vi.fn>;
  let listComunas: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    listAcademies = vi.fn((_query: AcademyQuery) =>
      of(makePage([makeAcademy()], { total: 1 })),
    );
    listStyles = vi.fn(() => of([{ slug: 'salsa', name: 'Salsa', sort: 1 }]));
    listComunas = vi.fn(() => of(['Providencia', 'Ñuñoa']));

    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        {
          provide: AcademiesApiService,
          useValue: { listAcademies, listStyles, listComunas },
        },
      ],
    });
  });

  afterEach(() => vi.useRealTimers());

  async function open(url: string): Promise<void> {
    harness = await RouterTestingHarness.create();
    componentInstance = await harness.navigateByUrl(url, AcademyListPage);
    await harness.fixture.whenStable();
  }

  function component(): AcademyListPage {
    return componentInstance;
  }

  function element(): HTMLElement {
    return harness.routeNativeElement as HTMLElement;
  }

  it('carga la primera página y renderiza una tarjeta', async () => {
    await open('/');

    expect(listAcademies).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, pageSize: 20 }),
    );
    expect(element().textContent).toContain('Dansón Academy');
  });

  it('lee los filtros y la página de la URL', async () => {
    await open('/?q=sa&comuna=Providencia&style=salsa&page=2');

    expect(listAcademies).toHaveBeenCalledWith(
      expect.objectContaining({
        comuna: 'Providencia',
        style: 'salsa',
        q: 'sa',
        page: 2,
        pageSize: 20,
      }),
    );
  });

  it('cambia la comuna, resetea la página y conserva los demás filtros', async () => {
    await open('/?q=sa&style=salsa&page=2');
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate');

    const select = element().querySelector('#filter-comuna') as HTMLSelectElement;
    select.value = 'Ñuñoa';
    select.dispatchEvent(new Event('change'));

    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({
        queryParams: expect.objectContaining({
          comuna: 'Ñuñoa',
          q: 'sa',
          style: 'salsa',
          page: 1,
        }),
      }),
    );
  });

  it('hace debounce de la búsqueda y no navega con un carácter', async () => {
    await open('/');
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    vi.useFakeTimers();
    component().onQ('s');
    vi.advanceTimersByTime(299);
    expect(navigate).not.toHaveBeenCalled();

    component().onQ('sa');
    vi.advanceTimersByTime(300);

    expect(navigate).toHaveBeenCalled();
    const lastCall = navigate.mock.calls.at(-1);
    expect(lastCall?.[1]).toEqual(
      expect.objectContaining({ queryParams: expect.objectContaining({ q: 'sa', page: 1 }) }),
    );
  });

  it('cancela la petición anterior al cambiar de filtro', async () => {
    const requests: Array<{ unsubscribed: boolean }> = [];
    listAcademies.mockImplementation(
      () =>
        new Observable(() => {
          const record = { unsubscribed: false };
          requests.push(record);
          return () => {
            record.unsubscribed = true;
          };
        }),
    );

    await open('/');
    expect(requests).toHaveLength(1);

    const router = TestBed.inject(Router);
    await router.navigateByUrl('/?page=2');
    await harness.fixture.whenStable();

    expect(requests.length).toBeGreaterThanOrEqual(2);
    expect(requests[0].unsubscribed).toBe(true);
  });

  it('redirige una página fuera de rango a la última', async () => {
    listAcademies.mockImplementation((query: AcademyQuery) =>
      of(makePage([], { page: query.page ?? 1, total: 45 })),
    );
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    await open('/?page=999');

    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({
        queryParams: expect.objectContaining({ page: 3 }),
        replaceUrl: true,
      }),
    );
    expect(listAcademies).toHaveBeenCalledTimes(1);
  });

  it('normaliza una URL inválida antes de consultar', async () => {
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    await open('/?q=a&style=Salsa!&page=0');

    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({
        queryParams: { page: 1 },
        replaceUrl: true,
      }),
    );
  });

  it('muestra el error y permite reintentar', async () => {
    listAcademies.mockImplementation(() =>
      throwError(() => new HttpErrorResponse({ status: 503 })),
    );

    await open('/');

    expect(element().textContent).toContain('no está disponible');
    const retry = Array.from(
      element().querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find(button => button.textContent?.includes('Reintentar')) as HTMLButtonElement;

    retry.click();
    await harness.fixture.whenStable();

    expect(listAcademies).toHaveBeenCalledTimes(2);
  });

  it('muestra el estado vacío con acción para limpiar filtros', async () => {
    listAcademies.mockImplementation(() => of(makePage([], { total: 0 })));
    await open('/?q=zz');

    expect(element().textContent).toContain('Sin resultados');

    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate');
    const clear = Array.from(
      element().querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find(button => button.textContent?.includes('Limpiar filtros')) as HTMLButtonElement;

    clear.click();

    expect(navigate).toHaveBeenCalledWith(['/']);
  });

  it('escribe el título, canonical y noindex según los filtros', async () => {
    await open('/');

    expect(document.title).toBe('Academias de baile en Santiago · Bailoteca');
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(
      'https://bailoteca.vercel.app/',
    );
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'index, follow',
    );

    await harness.navigateByUrl('/?comuna=Providencia', AcademyListPage);
    await harness.fixture.whenStable();

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'noindex, follow',
    );
  });

  it('marca noindex en páginas posteriores a la primera', async () => {
    listAcademies.mockImplementation(() => of(makePage([], { page: 2, total: 40 })));

    await open('/?page=2');

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'noindex, follow',
    );
  });

  it('publica WebSite con SearchAction y la imagen social', async () => {
    await open('/');

    const jsonLd = JSON.parse(
      document.querySelector('script[type="application/ld+json"]')!.textContent!,
    );
    expect(jsonLd['@type']).toBe('WebSite');
    expect(jsonLd.url).toBe('https://bailoteca.vercel.app/');
    expect(jsonLd.potentialAction).toEqual({
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: 'https://bailoteca.vercel.app/?q={search_term_string}',
      },
      'query-input': 'required name=search_term_string',
    });

    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(
      'https://bailoteca.vercel.app/og-image.png',
    );
  });
});
