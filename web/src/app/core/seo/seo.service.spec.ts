import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';

import { SeoService } from './seo.service';
import { SITE_URL } from './site-url';

describe('SeoService', () => {
  let service: SeoService;
  let doc: Document;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [{ provide: SITE_URL, useValue: 'https://bailoteca.test' }],
    });
    service = TestBed.inject(SeoService);
    doc = TestBed.inject(DOCUMENT);
  });

  afterEach(() => service.clear());

  it('escribe el título con el nombre del sitio', () => {
    service.set({ title: 'Academias de baile', description: 'Directorio', path: '/' });

    expect(doc.title).toBe('Academias de baile · Bailoteca');
  });

  it('escribe description, canonical y robots indexables', () => {
    service.set({ title: 'Academias', description: 'Directorio de academias', path: '/' });

    expect(doc.querySelector('meta[name="description"]')?.getAttribute('content')).toBe(
      'Directorio de academias',
    );
    expect(doc.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(
      'https://bailoteca.test/',
    );
    expect(doc.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'index, follow',
    );
  });

  it('marca noindex cuando se pide', () => {
    service.set({ title: 'No encontrada', description: 'x', path: '/x', noindex: true });

    expect(doc.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe(
      'noindex, follow',
    );
  });

  it('reemplaza los tags anteriores en vez de acumularlos', () => {
    service.set({ title: 'Uno', description: 'Primera', path: '/uno' });
    service.set({ title: 'Dos', description: 'Segunda', path: '/dos' });

    expect(doc.querySelectorAll('meta[name="description"]')).toHaveLength(1);
    expect(doc.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
    expect(doc.querySelector('meta[name="description"]')?.getAttribute('content')).toBe(
      'Segunda',
    );
    expect(doc.title).toBe('Dos · Bailoteca');
  });

  it('clear() elimina los tags gestionados y restaura el título por defecto', () => {
    service.set({ title: 'Uno', description: 'Primera', path: '/uno' });
    service.clear();

    expect(doc.querySelectorAll('[data-seo]')).toHaveLength(0);
    expect(doc.title).toBe('Bailoteca — Academias de baile en Santiago');
  });
});
