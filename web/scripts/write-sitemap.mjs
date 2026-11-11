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

const urls = routes
  .map(route => {
    const loc = new URL(route, SITE_URL).toString();
    const date = route === '/' ? homeLastmod : lastmod.get(route);
    const lastmodTag = date ? `<lastmod>${date}</lastmod>` : '';
    return `  <url><loc>${loc}</loc>${lastmodTag}</url>`;
  })
  .join('\n');

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;

const robots = `User-agent: *
Allow: /

# Crawlers de IA: mismo permiso de lectura que el resto del sitio.
User-agent: GPTBot
User-agent: ChatGPT-User
User-agent: ClaudeBot
User-agent: PerplexityBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: CCBot
Allow: /

Sitemap: ${new URL('/sitemap.xml', SITE_URL).toString()}
`;

writeFileSync(join(outputDir, 'sitemap.xml'), sitemap);
writeFileSync(join(outputDir, 'robots.txt'), robots);
console.log(
  `sitemap.xml con ${routes.length} rutas (${lastmod.size} con lastmod) y robots.txt escritos en ${outputDir}`,
);

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
