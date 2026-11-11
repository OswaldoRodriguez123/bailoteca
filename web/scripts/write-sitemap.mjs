import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const SITE_URL = process.env.SITE_URL ?? 'https://bailoteca.vercel.app';
const API_BASE_URL = process.env.API_BASE_URL?.replace(/\/$/, '');
const dist = new URL('../dist/bailoteca-web/', import.meta.url).pathname;
const routesFile = join(dist, 'prerendered-routes.json');
const outputDir = join(dist, 'browser');

if (!existsSync(routesFile)) {
  console.error('Falta dist/bailoteca-web/prerendered-routes.json: ¿se ejecutó el build?');
  process.exit(1);
}

const parsed = JSON.parse(readFileSync(routesFile, 'utf8'));
const routes = Object.keys(parsed.routes ?? parsed).filter(
  route => route === '/' || route === '/acerca' || route.startsWith('/academias/'),
);

const lastmod = await loadLastmod();
const homeLastmod = [...lastmod.values()].sort().at(-1);
const aboutLastmod = readAboutLastmod();

const urls = routes
  .map(route => {
    const loc = new URL(route, SITE_URL).toString();
    const date =
      route === '/' ? homeLastmod : route === '/acerca' ? aboutLastmod : lastmod.get(route);
    const lastmodTag = date ? `<lastmod>${date}</lastmod>` : '';
    return `  <url><loc>${loc}</loc>${lastmodTag}</url>`;
  })
  .join('\n');

const withLastmod = (urls.match(/<lastmod>/g) ?? []).length;

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;

const robots = `User-agent: *
Allow: /

# Crawlers de IA: mismo permiso de lectura que el resto del sitio.
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-User
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: Bytespider
Allow: /

User-agent: FacebookBot
Allow: /

User-agent: Amazonbot
Allow: /

Sitemap: ${new URL('/sitemap.xml', SITE_URL).toString()}
`;

// Página de 404 real: Vercel la sirve con estado 404 cuando ninguna ruta
// coincide. Sin ella, el `rewrites` a index.html respondía 200 con la portada
// (soft 404).
const notFound = `<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="robots" content="noindex" />
    <title>Página no encontrada · Bailoteca</title>
    <style>
      :root { color-scheme: light; }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 2rem;
        background: #fbf8f3;
        color: #1b1b1b;
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      }
      main { max-width: 32rem; }
      .eyebrow {
        margin: 0 0 0.5rem;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #8a5a2b;
      }
      h1 { margin: 0 0 1rem; font-size: clamp(2rem, 6vw, 3rem); line-height: 1.05; }
      p { margin: 0 0 1rem; line-height: 1.6; }
      a { color: #8a5a2b; font-weight: 600; }
    </style>
  </head>
  <body>
    <main>
      <p class="eyebrow">Error 404</p>
      <h1>Esta página no existe</h1>
      <p>
        Puede que la academia haya cambiado de nombre o que el enlace esté mal
        escrito.
      </p>
      <p><a href="/">Volver al directorio de academias</a> · <a href="/acerca">Acerca de Bailoteca</a></p>
    </main>
  </body>
</html>
`;

writeFileSync(join(outputDir, '404.html'), notFound);
writeFileSync(join(outputDir, 'sitemap.xml'), sitemap);
writeFileSync(join(outputDir, 'robots.txt'), robots);
console.log(
  `sitemap.xml con ${routes.length} rutas (${withLastmod} con lastmod), robots.txt y 404.html escritos en ${outputDir}`,
);

/**
 * La fecha de /acerca sale de la constante ABOUT_UPDATED_AT de la propia
 * página: es una fecha editable a mano, no la del build (que mentiría en cada
 * despliegue).
 */
function readAboutLastmod() {
  const source = readFileSync(
    new URL('../src/app/features/about/about.ts', import.meta.url),
    'utf8',
  );
  return source.match(/ABOUT_UPDATED_AT\s*=\s*'([0-9]{4}-[0-9]{2}-[0-9]{2})'/)?.[1];
}

async function loadLastmod() {
  const dates = new Map();

  if (!API_BASE_URL) {
    return dates;
  }

  try {
    let page = 1;
    let total = Number.POSITIVE_INFINITY;
    let seen = 0;

    while (seen < total) {
      const response = await fetch(
        `${API_BASE_URL}/academies?page=${page}&page_size=100`,
      );
      if (!response.ok) {
        break;
      }

      const data = await response.json();
      const items = data.items ?? [];
      total = data.total ?? 0;

      for (const academy of items) {
        const date = toDate(academy.updated_at ?? academy.verified_at);
        if (date) {
          dates.set(`/academias/${academy.slug}`, date);
        }
      }

      if (items.length === 0) {
        break;
      }

      seen += items.length;
      page += 1;
    }
  } catch {
    // Sin red o API caída: el sitemap se publica sin lastmod.
  }

  return dates;
}

function toDate(value) {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10);
}
