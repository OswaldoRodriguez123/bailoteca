import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const SITE_URL = process.env.SITE_URL ?? 'https://bailoteca.vercel.app';
const dist = new URL('../dist/bailoteca-web/', import.meta.url).pathname;
const routesFile = join(dist, 'prerendered-routes.json');
const outputDir = join(dist, 'browser');

if (!existsSync(routesFile)) {
  console.error('Falta dist/bailoteca-web/prerendered-routes.json: ¿se ejecutó el build?');
  process.exit(1);
}

const parsed = JSON.parse(readFileSync(routesFile, 'utf8'));
const routes = Object.keys(parsed.routes ?? parsed).filter(
  route => route === '/' || route.startsWith('/academias/'),
);

const urls = routes
  .map(route => `  <url><loc>${new URL(route, SITE_URL).toString()}</loc></url>`)
  .join('\n');

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;

const robots = `User-agent: *
Allow: /

Sitemap: ${new URL('/sitemap.xml', SITE_URL).toString()}
`;

writeFileSync(join(outputDir, 'sitemap.xml'), sitemap);
writeFileSync(join(outputDir, 'robots.txt'), robots);
console.log(`sitemap.xml con ${routes.length} rutas y robots.txt escritos en ${outputDir}`);
