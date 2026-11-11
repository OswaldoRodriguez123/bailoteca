import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { Subject, of, throwError } from 'rxjs';

import { routes } from '../../../app.routes';
import { AcademiesApiService } from '../../../core/services/academies-api';
import {
  makeAcademy,
  makeGoogle,
  makeLocation,
  makePage,
  makeStyle,
} from '../../../core/testing/academy.fixtures';
import { AcademyDetailPage } from './academy-detail';

describe('AcademyDetailPage', () => {
  let getAcademy: ReturnType<typeof vi.fn>;
  let listAcademies: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    getAcademy = vi.fn(() => of(makeAcademy()));
    listAcademies = vi.fn(() => of(makePage([])));

    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        { provide: AcademiesApiService, useValue: { getAcademy, listAcademies } },
      ],
    });
  });

  async function open(url: string): Promise<RouterTestingHarness> {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(url, AcademyDetailPage);
    await harness.fixture.whenStable();
    return harness;
  }

  function element(harness: RouterTestingHarness): HTMLElement {
    return harness.routeNativeElement as HTMLElement;
  }

  function linkTo(harness: RouterTestingHarness, text: string): HTMLAnchorElement {
    const link = Array.from(
      element(harness).querySelectorAll('a') as NodeListOf<HTMLAnchorElement>,
    ).find(candidate => candidate.textContent?.includes(text));
    expect(link, `enlace "${text}"`).toBeDefined();
    return link as HTMLAnchorElement;
  }

  it('carga la academia por slug y muestra el nombre como título', async () => {
    const harness = await open('/academias/danson-academy');

    expect(getAcademy).toHaveBeenCalledWith('danson-academy');
    expect(element(harness).querySelector('h1')?.textContent).toContain('Dansón Academy');
  });

  it('muestra estilos, direcciones y enlaces con etiquetas', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          description: 'Clases de salsa y bachata.',
          locations: [
            makeLocation({
              label: 'Sede Providencia',
              address: 'Av. Providencia 123',
              comuna: 'Providencia',
            }),
          ],
          links: [
            { kind: 'instagram', url: 'https://instagram.com/danson' },
            { kind: 'web', url: 'https://danson.cl' },
          ],
          styles: [makeStyle({ slug: 'salsa', name: 'Salsa' })],
        }),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const text = element(harness).textContent ?? '';

    expect(text).toContain('Clases de salsa y bachata.');
    expect(text).toContain('Salsa');
    expect(text).toContain('Sede Providencia');
    expect(text).toContain('Av. Providencia 123');
    expect(text).toContain('Providencia');
    expect(text).toContain('Instagram');
    expect(text).toContain('Sitio web');
  });

  it('muestra la portada cuando la academia tiene cover_url', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          cover_url:
            'https://proj.supabase.co/storage/v1/object/public/academy-covers/danson-academy.jpg',
        }),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const img = element(harness).querySelector('img') as HTMLImageElement | null;
    expect(img).not.toBeNull();
    expect(img!.getAttribute('src')).toBe(
      'https://proj.supabase.co/storage/v1/object/public/academy-covers/danson-academy.jpg',
    );
  });

  it('muestra las iniciales cuando la academia no tiene cover_url', async () => {
    getAcademy.mockReturnValue(of(makeAcademy({ cover_url: null })));

    const harness = await open('/academias/danson-academy');
    expect(element(harness).querySelector('img')).toBeNull();
    expect(element(harness).textContent).toContain('DA');
  });

  it('muestra las iniciales cuando la portada falla al cargar', async () => {
    getAcademy.mockReturnValue(
      of(makeAcademy({ cover_url: 'https://img.example/roto.jpg' })),
    );

    const harness = await open('/academias/danson-academy');
    const img = element(harness).querySelector('img');
    expect(img).not.toBeNull();

    img!.dispatchEvent(new Event('error'));
    await harness.fixture.whenStable();

    expect(element(harness).querySelector('img')).toBeNull();
    expect(element(harness).textContent).toContain('DA');
  });

  it('convierte teléfonos y emails en enlaces tel: y mailto:', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          links: [
            { kind: 'phone', url: '+56 9 1234 5678' },
            { kind: 'email', url: 'hola@danson.cl' },
          ],
        }),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const hrefs = Array.from(
      element(harness).querySelectorAll('a') as NodeListOf<HTMLAnchorElement>,
    ).map(link => link.getAttribute('href'));

    expect(hrefs).toContain('tel:+56912345678');
    expect(hrefs).toContain('mailto:hola@danson.cl');
  });

  it('muestra "Cómo llegar" solo cuando hay un mapa posible', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          locations: [
            makeLocation({ label: 'Con dirección', address: 'Av. Siempre Viva 123' }),
            makeLocation({ label: 'Sin nada', address: null, comuna: null, lat: null, lng: null }),
          ],
        }),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const mapLinks = Array.from(
      element(harness).querySelectorAll('a') as NodeListOf<HTMLAnchorElement>,
    ).filter(link => link.textContent?.includes('Cómo llegar'));

    expect(mapLinks).toHaveLength(1);
    expect(mapLinks[0].getAttribute('target')).toBe('_blank');
    expect(mapLinks[0].getAttribute('rel')).toContain('noopener');
  });

  it('muestra "Sin verificar" para academias sin verificar', async () => {
    getAcademy.mockReturnValue(of(makeAcademy({ status: 'unknown' })));
    const harness = await open('/academias/danson-academy');

    expect(element(harness).textContent).toContain('Sin verificar');
  });

  it('muestra "Verificado" cuando la academia tiene verified_at', async () => {
    getAcademy.mockReturnValue(
      of(makeAcademy({ status: 'unknown', verified_at: '2026-11-10T18:16:55Z' })),
    );
    const harness = await open('/academias/danson-academy');
    const text = element(harness).textContent ?? '';

    expect(text).toContain('Verificado');
    expect(text).not.toContain('Sin verificar');
  });

  it('no muestra "Cerrada" para academias activas', async () => {
    getAcademy.mockReturnValue(
      of(makeAcademy({ status: 'active', verified_at: '2026-11-10T18:16:55Z' })),
    );
    const harness = await open('/academias/danson-academy');
    const text = element(harness).textContent ?? '';

    expect(text).not.toContain('Cerrada');
    expect(text).toContain('Verificado');
  });

  it('no renderiza confianza, evidencia ni URLs de origen', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          source_urls: ['https://fuente.example/academia'],
          locations: [
            makeLocation({ source_url: 'https://fuente.example/sede', address: 'Av. Providencia 123' }),
          ],
          styles: [
            makeStyle({ slug: 'salsa', name: 'Salsa', confidence: 0.93, evidence: 'texto crudo' }),
          ],
        }),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const text = element(harness).textContent ?? '';

    expect(text).not.toContain('0.93');
    expect(text).not.toContain('texto crudo');
    expect(text).not.toContain('fuente.example');
    expect(element(harness).innerHTML).not.toContain('fuente.example');
  });

  it('muestra el estado no encontrado con enlace al listado', async () => {
    getAcademy.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found' })),
    );

    const harness = await open('/academias/inexistente');
    const text = element(harness).textContent ?? '';

    expect(text).toContain('No encontramos esa academia.');
    expect(text).not.toContain('Reintentar');
    expect(linkTo(harness, 'Volver al listado')).toBeTruthy();
  });

  it('muestra el error y permite reintentar manteniendo el enlace al listado', async () => {
    getAcademy.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 503, statusText: 'Unavailable' })),
    );

    const harness = await open('/academias/danson-academy');
    const text = element(harness).textContent ?? '';

    expect(text).toContain('no está disponible');
    expect(linkTo(harness, 'Volver al listado')).toBeTruthy();

    getAcademy.mockReturnValue(of(makeAcademy()));
    const retry = Array.from(
      element(harness).querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find(button => button.textContent?.includes('Reintentar')) as HTMLButtonElement;
    retry.click();
    await harness.fixture.whenStable();

    expect(getAcademy).toHaveBeenCalledTimes(2);
    expect(element(harness).querySelector('h1')?.textContent).toContain('Dansón Academy');
  });

  it('vuelve al listado conservando los filtros de la URL', async () => {
    const harness = await open('/academias/danson-academy?comuna=Providencia&page=2');

    const back = linkTo(harness, 'Volver al listado');
    expect(back.getAttribute('href')).toBe('/?comuna=Providencia&page=2');
  });

  it('renderiza una academia vacía sin lanzar', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          description: null,
          locations: [],
          links: [],
          styles: [],
          source_urls: [],
        }),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const text = element(harness).textContent ?? '';

    expect(text).toContain('Dansón Academy');
    expect(text).not.toContain('undefined');
  });

  it('escribe título, canonical y JSON-LD de la academia', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          name: 'Dansón Academy',
          description: 'Clases de salsa y bachata.',
          locations: [makeLocation({ comuna: 'Providencia', address: 'Av. Providencia 123' })],
          links: [{ kind: 'instagram', url: 'https://instagram.com/danson' }],
        }),
      ),
    );

    await open('/academias/danson-academy');

    expect(document.title).toBe('Dansón Academy — Providencia · Bailoteca');
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(
      'https://bailoteca.vercel.app/academias/danson-academy',
    );

    const jsonLd = JSON.parse(
      document.querySelector('script[type="application/ld+json"]')!.textContent!,
    );
    expect(jsonLd[0]['@type']).toBe('DanceSchool');
    expect(jsonLd[0].name).toBe('Dansón Academy');
    expect(jsonLd[0].address[0].addressLocality).toBe('Providencia');
    expect(jsonLd[0].sameAs).toEqual(['https://instagram.com/danson']);
  });

  it('declara @context en cada nodo del JSON-LD', async () => {
    getAcademy.mockReturnValue(
      of(makeAcademy({ name: 'Dansón Academy', slug: 'danson-academy' })),
    );

    await open('/academias/danson-academy');

    const jsonLd = JSON.parse(
      document.querySelector('script[type="application/ld+json"]')!.textContent!,
    ) as Record<string, unknown>[];
    const nodes = Array.isArray(jsonLd) ? jsonLd : [jsonLd];

    expect(nodes.map(node => node['@type'])).toEqual(['DanceSchool', 'BreadcrumbList']);
    for (const node of nodes) {
      expect(node['@context']).toBe('https://schema.org');
    }
  });

  it('completa el JSON-LD con los datos de Google y breadcrumbs', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          name: 'Dansón Academy',
          locations: [makeLocation({ comuna: 'Providencia', address: 'Av. Providencia 123' })],
          links: [
            { kind: 'instagram', url: 'https://instagram.com/danson' },
            { kind: 'facebook', url: 'https://facebook.com/share.php/' },
            { kind: 'phone', url: 'tel:+56912345678' },
          ],
          google: makeGoogle({
            rating: 4.8,
            reviews: 42,
            phone: '+56 9 1234 5678',
            maps_url: 'https://maps.google.com/?cid=1',
            hours: { lunes: '7–9 p. m.', martes: 'Cerrado' },
            gps_coordinates: { latitude: -33.43, longitude: -70.61 },
          }),
        }),
      ),
    );

    await open('/academias/danson-academy');

    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    expect(scripts).toHaveLength(1);

    const [jsonLd, breadcrumb] = JSON.parse(scripts[0].textContent!);
    expect(jsonLd.image).toBe('https://bailoteca.vercel.app/og-image.png');
    expect(jsonLd.telephone).toBe('+56912345678');
    expect(jsonLd.hasMap).toBe('https://maps.google.com/?cid=1');
    expect(jsonLd.geo).toEqual({
      '@type': 'GeoCoordinates',
      latitude: -33.43,
      longitude: -70.61,
    });
    expect(jsonLd.aggregateRating).toEqual({
      '@type': 'AggregateRating',
      ratingValue: 4.8,
      reviewCount: 42,
      bestRating: 5,
    });
    expect(jsonLd.openingHoursSpecification).toEqual([
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: 'https://schema.org/Monday',
        opens: '19:00',
        closes: '21:00',
      },
    ]);
    expect(jsonLd.sameAs).toEqual(['https://instagram.com/danson']);

    expect(breadcrumb['@type']).toBe('BreadcrumbList');
    expect(breadcrumb.itemListElement).toHaveLength(2);

    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(
      'https://bailoteca.vercel.app/og-image.png',
    );
    expect(document.querySelector('meta[property="og:type"]')?.getAttribute('content')).toBe(
      'place',
    );
  });

  it('enlaza academias de la misma comuna y excluye la actual', async () => {
    getAcademy.mockReturnValue(
      of(makeAcademy({ locations: [makeLocation({ comuna: 'Providencia' })] })),
    );
    listAcademies.mockReturnValue(
      of(
        makePage([
          makeAcademy({ slug: 'danson-academy', name: 'Dansón Academy' }),
          makeAcademy({ slug: 'otra-academia', name: 'Otra Academia' }),
        ]),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const hrefs = Array.from(element(harness).querySelectorAll('a')).map(link =>
      link.getAttribute('href'),
    );

    expect(listAcademies).toHaveBeenCalledWith(
      expect.objectContaining({ comuna: 'Providencia' }),
    );
    expect(hrefs).toContain('/academias/otra-academia');
    expect(hrefs).not.toContain('/academias/danson-academy');
    expect(element(harness).textContent).toContain('Otra Academia');
  });

  it('cae al estilo cuando la comuna no tiene otras academias', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          locations: [makeLocation({ comuna: 'La Reina' })],
          styles: [makeStyle({ slug: 'mambo' })],
        }),
      ),
    );
    listAcademies.mockImplementation(query =>
      of(
        makePage(
          query.comuna
            ? [makeAcademy({ slug: 'danson-academy' })]
            : [makeAcademy({ slug: 'otra-academia', name: 'Otra Academia' })],
        ),
      ),
    );

    const harness = await open('/academias/danson-academy');
    const hrefs = Array.from(element(harness).querySelectorAll('a')).map(link =>
      link.getAttribute('href'),
    );

    expect(listAcademies).toHaveBeenCalledWith(expect.objectContaining({ comuna: 'La Reina' }));
    expect(listAcademies).toHaveBeenCalledWith(expect.objectContaining({ style: 'mambo' }));
    expect(hrefs).toContain('/academias/otra-academia');
  });

  it('descarta las relacionadas de la academia anterior al navegar', async () => {
    const first = new Subject<ReturnType<typeof makePage>>();
    const second = new Subject<ReturnType<typeof makePage>>();

    getAcademy.mockImplementation((slug: string) =>
      of(
        makeAcademy({
          slug,
          locations: [makeLocation({ comuna: slug === 'primera' ? 'Providencia' : 'Ñuñoa' })],
        }),
      ),
    );
    listAcademies.mockImplementation((query: { comuna?: string }) =>
      query.comuna === 'Providencia' ? first : second,
    );

    const harness = await open('/academias/primera');
    await harness.navigateByUrl('/academias/segunda', AcademyDetailPage);
    await harness.fixture.whenStable();

    first.next(makePage([makeAcademy({ slug: 'vieja', name: 'Vieja' })]));
    second.next(makePage([makeAcademy({ slug: 'nueva', name: 'Nueva' })]));
    await harness.fixture.whenStable();

    const hrefs = Array.from(element(harness).querySelectorAll('a')).map(link =>
      link.getAttribute('href'),
    );
    expect(hrefs).toContain('/academias/nueva');
    expect(hrefs).not.toContain('/academias/vieja');
  });

  it('no rompe la página si las relacionadas fallan', async () => {
    getAcademy.mockReturnValue(
      of(makeAcademy({ locations: [makeLocation({ comuna: 'Providencia' })] })),
    );
    listAcademies.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));

    const harness = await open('/academias/danson-academy');

    expect(element(harness).querySelector('h1')?.textContent).toContain('Dansón Academy');
  });

  it('marca noindex cuando la academia no existe', async () => {
    getAcademy.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 404 })));

    await open('/academias/no-existe');

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'noindex, follow',
    );
  });

  it('trata la descripción y la comuna vacías como ausentes', async () => {
    getAcademy.mockReturnValue(
      of(
        makeAcademy({
          description: '   ',
          locations: [makeLocation({ comuna: '' })],
        }),
      ),
    );

    await open('/academias/danson-academy');

    expect(document.title).toBe('Dansón Academy — Santiago · Bailoteca');
    expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toBe(
      'Academia de baile en Santiago.',
    );

    const jsonLd = JSON.parse(
      document.querySelector('script[type="application/ld+json"]')!.textContent!,
    );
    expect(jsonLd[0].description).toBeUndefined();
  });

  it('recorta la meta description larga y deja el texto completo en el JSON-LD', async () => {
    const long = `${'Clases de salsa y bachata para principiantes en Providencia. '.repeat(4)}Fin.`;
    getAcademy.mockReturnValue(of(makeAcademy({ description: long })));

    await open('/academias/danson-academy');

    const meta = document.querySelector('meta[name="description"]')?.getAttribute('content') ?? '';
    expect(meta.length).toBeLessThanOrEqual(160);
    expect(meta.endsWith('…')).toBe(true);

    const jsonLd = JSON.parse(
      document.querySelector('script[type="application/ld+json"]')!.textContent!,
    );
    expect(jsonLd[0].description).toBe(long);
  });

  it('marca noindex cuando la academia falla con un error del servidor', async () => {
    getAcademy.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));

    await open('/academias/danson-academy');

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'noindex, follow',
    );
  });
});
