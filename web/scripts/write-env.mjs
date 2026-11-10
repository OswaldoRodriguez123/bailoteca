import { writeFileSync } from 'node:fs';

const url = process.env.API_BASE_URL;
if (!url) {
  console.error('API_BASE_URL es obligatoria para el build de producción.');
  process.exit(1);
}

const escaped = url.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const target = new URL('../src/environments/environment.production.ts', import.meta.url);
writeFileSync(
  target,
  `export const environment = {\n  production: true,\n  apiBaseUrl: '${escaped}',\n};\n`,
);
