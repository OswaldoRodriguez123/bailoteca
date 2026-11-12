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
    expect(doc.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('index, follow');
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
    expect(doc.querySelector('meta[name="description"]')?.getAttribute('content')).toBe('Segunda');
    expect(doc.title).toBe('Dos · Bailoteca');
  });

  it('clear() elimina los tags gestionados y restaura el título por defecto', () => {
    service.set({ title: 'Uno', description: 'Primera', path: '/uno' });
    service.clear();

    expect(doc.querySelectorAll('[data-seo]')).toHaveLength(0);
    expect(doc.title).toBe('Bailoteca — Academias de baile en Chile');
  });

  it('escribe Open Graph y Twitter Cards', () => {
    service.set({
      title: 'Dansón Academy',
      description: 'Clases de salsa en Providencia',
      path: '/academias/danson-academy',
    });

    expect(doc.querySelector('meta[property="og:title"]')?.getAttribute('content')).toBe(
      'Dansón Academy · Bailoteca',
    );
    expect(doc.querySelector('meta[property="og:description"]')?.getAttribute('content')).toBe(
      'Clases de salsa en Providencia',
    );
    expect(doc.querySelector('meta[property="og:url"]')?.getAttribute('content')).toBe(
      'https://bailoteca.test/academias/danson-academy',
    );
    expect(doc.querySelector('meta[property="og:type"]')?.getAttribute('content')).toBe('website');
    expect(doc.querySelector('meta[property="og:site_name"]')?.getAttribute('content')).toBe(
      'Bailoteca',
    );
    expect(doc.querySelector('meta[property="og:locale"]')?.getAttribute('content')).toBe('es_CL');
    expect(doc.querySelector('meta[name="twitter:card"]')?.getAttribute('content')).toBe(
      'summary_large_image',
    );
    expect(doc.querySelector('meta[name="twitter:title"]')?.getAttribute('content')).toBe(
      'Dansón Academy · Bailoteca',
    );
  });

  it('escribe og:image y twitter:image solo si hay imagen', () => {
    service.set({ title: 'A', description: 'B', path: '/a' });
    expect(doc.querySelector('meta[property="og:image"]')).toBeNull();

    service.set({ title: 'A', description: 'B', path: '/a', image: '/og.png' });
    expect(doc.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(
      'https://bailoteca.test/og.png',
    );
    expect(doc.querySelector('meta[name="twitter:image"]')?.getAttribute('content')).toBe(
      'https://bailoteca.test/og.png',
    );
  });

  it('escribe alt y dimensiones de la imagen social', () => {
    service.set({
      title: 'A',
      description: 'B',
      path: '/a',
      image: '/og.png',
      imageAlt: 'Bailoteca',
      imageWidth: 1200,
      imageHeight: 630,
    });

    expect(doc.querySelector('meta[property="og:image:alt"]')?.getAttribute('content')).toBe(
      'Bailoteca',
    );
    expect(doc.querySelector('meta[property="og:image:width"]')?.getAttribute('content')).toBe(
      '1200',
    );
    expect(doc.querySelector('meta[property="og:image:height"]')?.getAttribute('content')).toBe(
      '630',
    );
  });

  it('permite cambiar og:type', () => {
    service.set({ title: 'A', description: 'B', path: '/a', type: 'place' });

    expect(doc.querySelector('meta[property="og:type"]')?.getAttribute('content')).toBe('place');
  });

  it('escribe un objeto JSON-LD en un script', () => {
    service.set({
      title: 'Dansón Academy',
      description: 'Clases de salsa',
      path: '/academias/danson-academy',
      jsonLd: { '@context': 'https://schema.org', '@type': 'DanceSchool', name: 'Dansón Academy' },
    });

    const script = doc.querySelector('script[type="application/ld+json"]');
    expect(script).not.toBeNull();
    expect(JSON.parse(script!.textContent!)).toEqual({
      '@context': 'https://schema.org',
      '@type': 'DanceSchool',
      name: 'Dansón Academy',
    });
  });

  it('escribe un array de objetos JSON-LD', () => {
    service.set({
      title: 'A',
      description: 'B',
      path: '/a',
      jsonLd: [{ '@type': 'WebSite' }, { '@type': 'BreadcrumbList' }],
    });

    const script = doc.querySelector('script[type="application/ld+json"]');
    expect(JSON.parse(script!.textContent!)).toHaveLength(2);
  });

  it('reemplaza el JSON-LD anterior', () => {
    service.set({ title: 'A', description: 'B', path: '/a', jsonLd: { '@type': 'WebSite' } });
    service.set({ title: 'C', description: 'D', path: '/c', jsonLd: { '@type': 'DanceSchool' } });

    expect(doc.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(1);
    expect(
      JSON.parse(doc.querySelector('script[type="application/ld+json"]')!.textContent!),
    ).toEqual({
      '@type': 'DanceSchool',
    });
  });
});
