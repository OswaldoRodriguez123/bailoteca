/**
 * Genera el contenido de /llms.txt.
 *
 * Vive fuera de `src/` porque lo consume el postbuild (Node), no Angular. Las
 * URLs salen de `site.config.json` o de `SITE_URL` / `API_BASE_URL`, así que un
 * cambio de dominio no requiere editar este archivo.
 */
export function renderLlms({ siteUrl, apiBaseUrl }) {
  const site = trimTrailingSlash(siteUrl);
  const api = trimTrailingSlash(apiBaseUrl);

  return `# Bailoteca

> Directorio de academias de baile en Chile, organizado por región, comuna y estilo.

Bailoteca reúne fichas de academias de salsa, bachata, tango, mambo y otros ritmos
latinos en todo Chile. Cada ficha incluye sedes, comunas, estilos, horarios, teléfono,
sitio web y perfiles sociales cuando el dato está disponible.

## Directorio

- [Academias de baile en Chile](${site}/): listado con filtros por región, comuna y estilo.
- [Sitemap](${site}/sitemap.xml): todas las fichas publicadas y su última actualización.
- [API pública](${api}/academies): datos abiertos de academias en JSON.

## Cómo está organizado

Las fichas usan la URL \`/academias/<slug>\`, por ejemplo
\`/academias/as-you-wish\`. Los filtros del listado (\`?region=\`, \`?comuna=\`, \`?style=\`, \`?q=\` y
\`?page=\`) no se indexan; la versión canónica de cada academia es su ficha.

## Uso de los datos

Los datos de contacto provienen de fuentes públicas y de Google Places. Bailoteca
es un directorio independiente: no vende cursos ni gestiona reservas.
`;
}

function trimTrailingSlash(url) {
  return url.replace(/\/$/, '');
}
