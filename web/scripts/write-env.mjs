/**
 * Escribe `src/environments/environment.production.ts` antes del build.
 *
 * Los valores salen de `site.config.json` y se pueden pisar con `SITE_URL` y
 * `API_BASE_URL`: para cambiar de dominio basta editar el JSON (o definir las
 * variables en el host) y este archivo se regenera solo.
 */
import { readFileSync, writeFileSync } from 'node:fs';

const config = JSON.parse(readFileSync(new URL('../site.config.json', import.meta.url), 'utf8'));

const apiBaseUrl = process.env.API_BASE_URL ?? config.apiBaseUrl;
const siteUrl = process.env.SITE_URL ?? config.siteUrl;

if (!apiBaseUrl || !siteUrl) {
  console.error('Falta apiBaseUrl o siteUrl: revisa web/site.config.json.');
  process.exit(1);
}

const escaped = (value) => value.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const target = new URL('../src/environments/environment.production.ts', import.meta.url);
writeFileSync(
  target,
  `export const environment = {\n  production: true,\n  siteUrl: '${escaped(siteUrl)}',\n  apiBaseUrl: '${escaped(apiBaseUrl)}',\n};\n`,
);
