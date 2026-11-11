import { makeAcademy, makeLocation } from '../../core/testing/academy.fixtures';
import {
  breadcrumbList,
  linkHref,
  linkLabel,
  mapUrl,
  normalizePhone,
  openingHoursSpecification,
  socialProfiles,
  styleLabel,
  truncated,
  uniqueComunas,
} from './academy-display';

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

  it('convierte teléfonos y emails en enlaces tel: y mailto:', () => {
    expect(linkHref({ kind: 'phone', url: '+56 9 1234 5678' })).toBe('tel:+56912345678');
    expect(linkHref({ kind: 'email', url: 'hola@danson.cl' })).toBe('mailto:hola@danson.cl');
    expect(linkHref({ kind: 'phone', url: 'tel:+56987654321' })).toBe('tel:+56987654321');
    expect(linkHref({ kind: 'web', url: 'https://danson.cl' })).toBe('https://danson.cl');
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

  it('deja en sameAs solo perfiles http(s) y descarta enlaces de compartir', () => {
    const profiles = socialProfiles([
      { kind: 'instagram', url: 'https://instagram.com/danson' },
      { kind: 'facebook', url: 'https://facebook.com/share.php/' },
      { kind: 'facebook', url: 'https://facebook.com/danson' },
      { kind: 'phone', url: 'tel:+56912345678' },
      { kind: 'email', url: 'mailto:hola@danson.cl' },
      { kind: 'instagram', url: 'https://instagram.com/danson' },
    ]);

    expect(profiles).toEqual([
      'https://instagram.com/danson',
      'https://facebook.com/danson',
    ]);
  });

  it('convierte horarios legibles en OpeningHoursSpecification', () => {
    const spec = openingHoursSpecification({
      lunes: '7–9 p. m.',
      martes: '9 a. m.–6 p. m.',
      miércoles: '10:00–20:00',
      jueves: 'Cerrado',
      viernes: 'a convenir',
    });

    expect(spec).toEqual([
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: 'https://schema.org/Monday',
        opens: '19:00',
        closes: '21:00',
      },
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: 'https://schema.org/Tuesday',
        opens: '09:00',
        closes: '18:00',
      },
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: 'https://schema.org/Wednesday',
        opens: '10:00',
        closes: '20:00',
      },
    ]);
  });

  it('no inventa horarios cuando no hay datos', () => {
    expect(openingHoursSpecification(null)).toEqual([]);
    expect(openingHoursSpecification({})).toEqual([]);
  });

  it('acepta días en inglés además de español', () => {
    const spec = openingHoursSpecification({ monday: '7–9 p. m.', Sunday: 'Cerrado' });

    expect(spec).toEqual([
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: 'https://schema.org/Monday',
        opens: '19:00',
        closes: '21:00',
      },
    ]);
  });

  it('normaliza teléfonos chilenos a E.164', () => {
    expect(normalizePhone('9 9679 1861')).toBe('+56996791861');
    expect(normalizePhone('+56 9 1234 5678')).toBe('+56912345678');
    expect(normalizePhone('56912345678')).toBe('+56912345678');
    expect(normalizePhone('223456789')).toBe('+56223456789');
    expect(normalizePhone(null)).toBeNull();
    expect(normalizePhone('   ')).toBeNull();
  });

  it('arma un BreadcrumbList con la portada y la academia', () => {
    expect(breadcrumbList('Dansón Academy', '/academias/danson-academy', 'https://bailoteca.test')).toEqual({
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'Inicio',
          item: 'https://bailoteca.test/',
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'Dansón Academy',
          item: 'https://bailoteca.test/academias/danson-academy',
        },
      ],
    });
  });
});
