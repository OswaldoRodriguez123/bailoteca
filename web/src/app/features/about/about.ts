import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { SeoService } from '../../core/seo/seo.service';
import { SITE_URL } from '../../core/seo/site-url';

/** Fecha de la última edición del contenido de esta página; la usa el sitemap. */
export const ABOUT_UPDATED_AT = '2026-11-11';

const EMAIL = 'oswaldo_rodriguez_1@hotmail.com';
const GITHUB = 'https://github.com/OswaldoRodriguez123';
const LINKEDIN = 'https://www.linkedin.com/in/oswaldorodriguez20';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-about',
  template: `
    <section class="mx-auto max-w-3xl space-y-10">
      <header class="space-y-4">
        <p class="text-sm font-medium uppercase tracking-[0.18em] text-accent-ink">Acerca de</p>
        <h1
          class="text-balance font-display text-4xl font-extrabold leading-[0.95] tracking-tight text-ink sm:text-6xl"
        >
          Acerca de Bailoteca
        </h1>
        <p class="max-w-2xl text-lg leading-relaxed text-ink-soft">
          Un directorio independiente de academias de baile en Santiago de Chile, organizado por
          comuna y estilo.
        </p>
      </header>

      <div class="space-y-8 border-t border-line pt-8">
        <section class="space-y-3">
          <h2 class="font-display text-2xl font-bold tracking-tight text-ink">Qué es Bailoteca</h2>
          <p class="leading-relaxed text-ink-soft">
            Bailoteca reúne academias de salsa, bachata, tango, mambo y otros ritmos latinos de
            Santiago. Cada ficha muestra sedes, comunas, estilos, horarios, teléfono, sitio web y
            perfiles sociales cuando el dato está disponible, para que puedas comparar y elegir una
            clase cerca de ti.
          </p>
        </section>

        <section class="space-y-3">
          <h2 class="font-display text-2xl font-bold tracking-tight text-ink">
            Cómo se elabora el directorio
          </h2>
          <p class="leading-relaxed text-ink-soft">
            Las fichas combinan datos de fuentes públicas y de Google Places. No se cobra por
            aparecer y no se inventan datos: cuando un campo no está disponible, simplemente no se
            muestra. La fecha de última actualización de cada academia se publica en el
            <a
              href="/sitemap.xml"
              class="font-medium text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
            >
              sitemap
            </a>.
          </p>
        </section>

        <section class="space-y-3">
          <h2 class="font-display text-2xl font-bold tracking-tight text-ink">
            Quién lo mantiene
          </h2>
          <p class="leading-relaxed text-ink-soft">
            Bailoteca es un proyecto de
            <strong class="font-semibold text-ink" translate="no">Oswaldo Rodríguez</strong>,
            Software Developer en Santiago de Chile. Lo diseño, lo construyo y mantengo el catálogo.
          </p>
          <p class="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            <a
              href="https://github.com/OswaldoRodriguez123"
              rel="me noopener"
              class="font-medium text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
            >
              GitHub
            </a>
            <a
              href="https://www.linkedin.com/in/oswaldorodriguez20"
              rel="me noopener"
              class="font-medium text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
            >
              LinkedIn
            </a>
          </p>
        </section>

        <section class="space-y-3">
          <h2 class="font-display text-2xl font-bold tracking-tight text-ink">
            Correcciones y contacto
          </h2>
          <p class="leading-relaxed text-ink-soft">
            Si eres dueño de una academia y quieres corregir o retirar tu ficha, escribe a
            <a
              href="mailto:oswaldo_rodriguez_1@hotmail.com"
              class="font-medium text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
            >
              oswaldo_rodriguez_1@hotmail.com
            </a>
            con el nombre de la academia y su URL en Bailoteca.
          </p>
        </section>
      </div>
    </section>
  `,
})
export class AboutPage {
  private readonly seo = inject(SeoService);
  private readonly siteUrl = inject(SITE_URL);

  constructor() {
    this.seo.set({
      title: 'Acerca de Bailoteca',
      description:
        'Qué es Bailoteca, cómo se recopilan los datos de las academias de baile de Santiago y cómo pedir una corrección.',
      path: '/acerca',
      jsonLd: [
        {
          '@context': 'https://schema.org',
          '@type': 'AboutPage',
          name: 'Acerca de Bailoteca',
          url: `${this.siteUrl}/acerca`,
          inLanguage: 'es-CL',
          mainEntity: { '@id': `${this.siteUrl}/#person` },
        },
        {
          '@context': 'https://schema.org',
          '@type': 'Person',
          '@id': `${this.siteUrl}/#person`,
          name: 'Oswaldo Rodríguez',
          jobTitle: 'Software Developer',
          email: EMAIL,
          url: GITHUB,
          address: {
            '@type': 'PostalAddress',
            addressLocality: 'Santiago',
            addressCountry: 'CL',
          },
          sameAs: [GITHUB, LINKEDIN],
        },
      ],
    });
  }
}
