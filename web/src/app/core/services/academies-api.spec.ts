import { HttpErrorResponse } from '@angular/common/http';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API_BASE_URL } from '../api-base-url';
import { makeAcademy } from '../testing/academy.fixtures';
import { AcademiesApiService } from './academies-api';

describe('AcademiesApiService', () => {
  let service: AcademiesApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        AcademiesApiService,
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: 'http://api.test/' },
      ],
    });

    service = TestBed.inject(AcademiesApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista academias con page_size y omite filtros vacíos', () => {
    let total = -1;

    service.listAcademies({ comuna: 'Providencia', q: '', page: 2 }).subscribe(page => {
      total = page.total;
    });

    const req = http.expectOne(request => request.url === 'http://api.test/academies');

    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('comuna')).toBe('Providencia');
    expect(req.request.params.get('q')).toBeNull();
    expect(req.request.params.get('region')).toBeNull();
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe('20');

    req.flush({ items: [], page: 2, page_size: 20, total: 0 });
    expect(total).toBe(0);
  });

  it('envía la región en /academies cuando está presente', () => {
    service.listAcademies({ region: 'biobio', page: 1 }).subscribe();

    const req = http.expectOne(request => request.url === 'http://api.test/academies');

    expect(req.request.params.get('region')).toBe('biobio');
    req.flush({ items: [], page: 1, page_size: 20, total: 0 });
  });

  it('envía sort y coordenadas cuando están presentes', () => {
    service.listAcademies({ sort: 'cercanas', lat: -33.45, lng: -70.66, page: 1 }).subscribe();
    const req = http.expectOne(r => r.url === 'http://api.test/academies');
    expect(req.request.params.get('sort')).toBe('cercanas');
    expect(req.request.params.get('lat')).toBe('-33.45');
    expect(req.request.params.get('lng')).toBe('-70.66');
    req.flush({ items: [], page: 1, page_size: 20, total: 0 });
  });

  it('envía la región por defecto en /comunas', () => {
    service.listComunas().subscribe();

    const req = http.expectOne(request => request.url === 'http://api.test/comunas');

    expect(req.request.params.get('region')).toBe('metropolitana');
    req.flush({ items: ['Providencia'] });
  });

  it('envía la región indicada en /comunas', () => {
    service.listComunas('all').subscribe();

    const req = http.expectOne(request => request.url === 'http://api.test/comunas');

    expect(req.request.params.get('region')).toBe('all');
    req.flush({ items: [] });
  });

  it('usa page 1 y page_size 20 por defecto', () => {
    service.listAcademies().subscribe();

    const req = http.expectOne(request => request.url === 'http://api.test/academies');
    expect(req.request.params.get('page')).toBe('1');
    expect(req.request.params.get('page_size')).toBe('20');
    req.flush({ items: [], page: 1, page_size: 20, total: 0 });
  });

  it('obtiene el detalle por slug', () => {
    const academy = makeAcademy();
    let received = null;

    service.getAcademy('danson-academy').subscribe(result => {
      received = result;
    });

    const req = http.expectOne(
      request => request.url === 'http://api.test/academies/danson-academy',
    );
    expect(req.request.method).toBe('GET');
    req.flush(academy);

    expect(received).toEqual(academy);
  });

  it('mapea estilos y comunas desde items', () => {
    let styles: string[] = [];
    let comunas: string[] = [];

    service.listStyles().subscribe(items => {
      styles = items.map(item => item.slug);
    });
    http
      .expectOne(request => request.url === 'http://api.test/styles')
      .flush({ items: [{ slug: 'salsa', name: 'Salsa', sort: 1 }] });

    service.listComunas('valparaiso').subscribe(items => {
      comunas = items;
    });
    const comunasReq = http.expectOne(request => request.url === 'http://api.test/comunas');
    expect(comunasReq.request.params.get('region')).toBe('valparaiso');
    comunasReq.flush({ items: ['Providencia'] });

    expect(styles).toEqual(['salsa']);
    expect(comunas).toEqual(['Providencia']);
  });

  it('propaga errores de la API', () => {
    let status = 0;

    service.listAcademies().subscribe({
      error: (error: HttpErrorResponse) => {
        status = error.status;
      },
    });

    http
      .expectOne(request => request.url === 'http://api.test/academies')
      .flush({ detail: 'Base de datos no disponible' }, { status: 503, statusText: 'Unavailable' });

    expect(status).toBe(503);
  });
});
