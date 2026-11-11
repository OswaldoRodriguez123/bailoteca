import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { routes } from '../../app.routes';
import { AboutPage } from './about';

describe('AboutPage', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter(routes)] });
  });

  async function open(): Promise<RouterTestingHarness> {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/acerca', AboutPage);
    await harness.fixture.whenStable();
    return harness;
  }

  it('presenta al responsable y sus canales de contacto', async () => {
    const harness = await open();
    const element = harness.routeNativeElement as HTMLElement;
    const hrefs = Array.from(element.querySelectorAll('a')).map(link =>
      link.getAttribute('href'),
    );

    expect(element.querySelector('h1')?.textContent).toContain('Acerca de Bailoteca');
    expect(element.textContent).toContain('Oswaldo Rodríguez');
    expect(element.textContent).toContain('Software Developer');
    expect(element.textContent).toContain('Santiago de Chile');
    expect(hrefs).toContain('mailto:oswaldo_rodriguez_1@hotmail.com');
    expect(hrefs).toContain('https://github.com/OswaldoRodriguez123');
    expect(hrefs).toContain('https://www.linkedin.com/in/oswaldorodriguez20');
  });

  it('publica título, canonical y datos estructurados de la página y la persona', async () => {
    await open();

    expect(document.title).toBe('Acerca de Bailoteca · Bailoteca');
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(
      'https://bailoteca.vercel.app/acerca',
    );

    const jsonLd = JSON.parse(
      document.querySelector('script[type="application/ld+json"]')!.textContent!,
    ) as Array<Record<string, unknown>>;

    expect(jsonLd.map(item => item['@type'])).toEqual(['AboutPage', 'Person']);

    const person = jsonLd[1];
    expect(person['name']).toBe('Oswaldo Rodríguez');
    expect(person['jobTitle']).toBe('Software Developer');
    expect(person['email']).toBe('oswaldo_rodriguez_1@hotmail.com');
    expect(person['address']).toEqual({
      '@type': 'PostalAddress',
      addressLocality: 'Santiago',
      addressCountry: 'CL',
    });
    expect(person['sameAs']).toEqual([
      'https://github.com/OswaldoRodriguez123',
      'https://www.linkedin.com/in/oswaldorodriguez20',
    ]);
  });
});
