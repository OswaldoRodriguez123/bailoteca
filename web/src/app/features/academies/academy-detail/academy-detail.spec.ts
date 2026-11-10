import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, throwError } from 'rxjs';

import { routes } from '../../../app.routes';
import { AcademiesApiService } from '../../../core/services/academies-api';
import { makeAcademy, makeLocation, makeStyle } from '../../../core/testing/academy.fixtures';
import { AcademyDetailPage } from './academy-detail';

describe('AcademyDetailPage', () => {
  let getAcademy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    getAcademy = vi.fn(() => of(makeAcademy()));

    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        { provide: AcademiesApiService, useValue: { getAcademy } },
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
});
