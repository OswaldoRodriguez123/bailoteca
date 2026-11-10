import { makeAcademy, makeLocation } from '../../core/testing/academy.fixtures';
import { linkLabel, mapUrl, styleLabel, truncated, uniqueComunas } from './academy-display';

describe('academy display helpers', () => {
  it('usa el nombre del estilo o capitaliza el slug', () => {
    expect(styleLabel({ slug: 'salsa', name: null, confidence: null, evidence: null })).toBe(
      'Salsa',
    );
    expect(
      styleLabel({ slug: 'bachata', name: 'Bachata sensual', confidence: null, evidence: null }),
    ).toBe('Bachata sensual');
  });

  it('etiqueta los tipos de enlace conocidos', () => {
    expect(linkLabel('instagram')).toBe('Instagram');
    expect(linkLabel('web')).toBe('Sitio web');
    expect(linkLabel('desconocido')).toBe('Enlace');
  });

  it('arma un enlace de mapa con coordenadas', () => {
    const url = mapUrl({ ...makeLocation(), lat: -33.4, lng: -70.6 });
    expect(url).toContain('query=-33.4,-70.6');
  });

  it('arma un enlace de mapa con dirección cuando faltan coordenadas', () => {
    const url = mapUrl({
      ...makeLocation(),
      lat: null,
      lng: null,
      address: 'Av. Siempre Viva 123',
    });
    expect(url).toContain('Av.+Siempre+Viva+123');
  });

  it('no arma enlace de mapa sin coordenadas ni dirección', () => {
    expect(
      mapUrl({ ...makeLocation(), lat: null, lng: null, address: null, comuna: null }),
    ).toBeNull();
  });

  it('devuelve comunas únicas en orden de aparición', () => {
    const academy = makeAcademy({
      locations: [
        makeLocation({ comuna: 'Providencia' }),
        makeLocation({ comuna: 'Providencia' }),
        makeLocation({ comuna: 'Ñuñoa' }),
        makeLocation({ comuna: null }),
      ],
    });

    expect(uniqueComunas(academy)).toEqual(['Providencia', 'Ñuñoa']);
  });

  it('recorta descripciones largas y tolera null', () => {
    expect(truncated(null)).toBe('');
    expect(truncated('x'.repeat(200), 20)).toHaveLength(21);
    expect(truncated('corto')).toBe('corto');
  });
});
