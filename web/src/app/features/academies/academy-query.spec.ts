import { convertToParamMap } from '@angular/router';

import { lastPage, ListQuery, normalizeQuery, queryToParams, sameQuery } from './academy-query';

describe('academy query helpers', () => {
  it('normaliza una URL vacía', () => {
    expect(normalizeQuery(convertToParamMap({}))).toEqual({
      region: 'metropolitana',
      comuna: null,
      style: null,
      q: null,
      sort: 'destacadas',
      lat: null,
      lng: null,
      page: 1,
    });
  });

  it('descarta una búsqueda de menos de 2 caracteres', () => {
    expect(normalizeQuery(convertToParamMap({ q: 'a' })).q).toBeNull();
  });

  it('descarta estilos inválidos', () => {
    expect(normalizeQuery(convertToParamMap({ style: 'Salsa!' })).style).toBeNull();
  });

  it('normaliza una página inválida a 1', () => {
    expect(normalizeQuery(convertToParamMap({ page: '0' })).page).toBe(1);
    expect(normalizeQuery(convertToParamMap({ page: 'x' })).page).toBe(1);
  });

  it('recorta espacios y acepta valores válidos', () => {
    expect(
      normalizeQuery(
        convertToParamMap({ comuna: ' Providencia ', style: 'salsa', q: ' bachata ', page: '2' }),
      ),
    ).toEqual({
      region: 'metropolitana',
      comuna: 'Providencia',
      style: 'salsa',
      q: 'bachata',
      sort: 'destacadas',
      lat: null,
      lng: null,
      page: 2,
    });
  });

  it('conserva una región válida', () => {
    expect(normalizeQuery(convertToParamMap({ region: 'valparaiso' })).region).toBe('valparaiso');
    expect(normalizeQuery(convertToParamMap({ region: 'all' })).region).toBe('all');
  });

  it('normaliza una región inválida a la Metropolitana', () => {
    expect(normalizeQuery(convertToParamMap({ region: 'atlantis' })).region).toBe('metropolitana');
  });

  it('serializa solo los valores presentes y siempre la página', () => {
    expect(
      queryToParams({
        region: 'metropolitana',
        comuna: null,
        style: 'salsa',
        q: 'bachata',
        sort: 'destacadas',
        lat: null,
        lng: null,
        page: 2,
      }),
    ).toEqual({
      style: 'salsa',
      q: 'bachata',
      page: 2,
    });
  });

  it('omite la región por defecto y emite las demás, incluido "all"', () => {
    const base: ListQuery = {
      region: 'metropolitana',
      comuna: null,
      style: null,
      q: null,
      sort: 'destacadas',
      lat: null,
      lng: null,
      page: 1,
    };

    expect(queryToParams(base)).toEqual({ page: 1 });
    expect(queryToParams({ ...base, region: 'all' })).toEqual({ region: 'all', page: 1 });
    expect(queryToParams({ ...base, region: 'biobio' })).toEqual({ region: 'biobio', page: 1 });
  });

  it('compara queries por valor', () => {
    const query: ListQuery = {
      region: 'metropolitana',
      comuna: 'Providencia',
      style: null,
      q: 'salsa',
      sort: 'destacadas',
      lat: null,
      lng: null,
      page: 1,
    };
    expect(sameQuery(query, { ...query })).toBe(true);
    expect(sameQuery(query, { ...query, page: 2 })).toBe(false);
    expect(sameQuery(query, { ...query, region: 'all' })).toBe(false);
  });

  it('usa destacadas por defecto y lo omite de la URL', () => {
    const query = normalizeQuery(convertToParamMap({}));
    expect(query.sort).toBe('destacadas');
    expect(queryToParams(query)).toEqual({ page: 1 });
  });

  it('descarta un orden inválido', () => {
    expect(normalizeQuery(convertToParamMap({ sort: 'precio' })).sort).toBe('destacadas');
  });

  it('exige coordenadas válidas para cercanas', () => {
    expect(normalizeQuery(convertToParamMap({ sort: 'cercanas' })).sort).toBe('destacadas');
    expect(
      normalizeQuery(convertToParamMap({ sort: 'cercanas', lat: '999', lng: '-70.6' })).sort,
    ).toBe('destacadas');
  });

  it('conserva cercanas y redondea las coordenadas a 6 decimales', () => {
    const query = normalizeQuery(
      convertToParamMap({ sort: 'cercanas', lat: '-33.4501234', lng: '-70.6609876' }),
    );
    expect(query).toEqual({
      region: 'metropolitana', comuna: null, style: null, q: null,
      sort: 'cercanas', lat: -33.4501234, lng: -70.6609876, page: 1,
    });
    expect(queryToParams(query)).toEqual({
      sort: 'cercanas', lat: '-33.450123', lng: '-70.660988', page: 1,
    });
  });

  it('ignora lat/lng cuando el orden no es cercanas', () => {
    const query = normalizeQuery(convertToParamMap({ sort: 'nuevas', lat: '-33.4', lng: '-70.6' }));
    expect([query.lat, query.lng]).toEqual([null, null]);
  });

  it('calcula la última página', () => {
    expect(lastPage(0)).toBe(1);
    expect(lastPage(20)).toBe(1);
    expect(lastPage(45)).toBe(3);
  });
});
