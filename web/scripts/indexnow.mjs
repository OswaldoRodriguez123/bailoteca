import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const KEY = '2e126af20d40499e8f218b6c96ae4515';
const SITE_URL = process.env.SITE_URL ?? 'https://bailoteca.vercel.app';
const ENDPOINT = 'https://api.indexnow.org/indexnow';
const dist = new URL('../dist/bailoteca-web/browser/', import.meta.url).pathname;

// Vercel only sets VERCEL_ENV during its own builds. CI and local runs skip the
// ping so preview deployments never advertise URLs that are not live yet.
if (process.env.VERCEL_ENV !== 'production' && process.env.INDEXNOW_FORCE !== '1') {
  console.log('indexnow: se omite porque el build no es de producción');
  process.exit(0);
}

try {
  const sitemap = readFileSync(join(dist, 'sitemap.xml'), 'utf8');
  const urlList = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)]
    .map(match => match[1].trim())
    .slice(0, 10_000);

  if (urlList.length === 0) {
    console.log('indexnow: el sitemap no tiene URLs');
    process.exit(0);
  }

  const response = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({
      host: new URL(SITE_URL).host,
      key: KEY,
      keyLocation: new URL(`${KEY}.txt`, SITE_URL).toString(),
      urlList,
    }),
  });

  console.log(
    `indexnow: ${response.status} ${response.statusText} (${urlList.length} URLs)`,
  );
} catch (error) {
  // Un fallo de IndexNow nunca debe tumbar el despliegue.
  console.warn(`indexnow: no se pudo notificar (${error.message})`);
}
