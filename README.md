# Bailoteca

**Bailoteca** es el backend de un directorio de academias de baile en Santiago,
empezando por salsa. Descubre candidatos desde fuentes gratuitas, los clasifica
por estilo con evidencia y deja propuestas para que una persona las apruebe
antes de publicarlas.

- **Publicado** = existe en la tabla `academies`. Solo la CLI escribe ahí,
  después de aprobar.
- **Estilos** multilabel sobre una taxonomía en la tabla `styles`
  (`salsa-cubana`, `salsa-linea`, `mambo`). Agregar bachata o kizomba es
  insertar filas, no migrar columnas.
- **Costo $0**: Postgres free en Supabase, GitHub Actions y fuentes gratuitas.
  Gemini es opcional; sin clave el sistema clasifica solo con reglas.

## Requisitos

- Python 3.12 o superior.
- Un proyecto de Supabase (free) o cualquier Postgres 14+.
- Opcional: una API key de Gemini para mejorar la clasificación.

## Puesta en marcha

1. Crear el proyecto en Supabase y copiar la cadena de conexión
   (`Project Settings → Database → Connection string`).
2. Aplicar las migraciones en orden desde el SQL Editor:

   ```text
   supabase/migrations/0001_schema.sql
   supabase/migrations/0002_rls.sql
   ```

   `0002` activa RLS y deja a la llave anónima solo lectura de las tablas
   publicadas.

3. Copiar `.env.example` a `.env` y llenar los valores:

   ```bash
   cp .env.example .env
   ```

   `DATABASE_URL` es un secreto: no se versiona ni se pega en el chat. La llave
   anónima de Supabase sirve para leer desde el frontend, nunca para escribir.

4. Instalar el paquete:

   ```bash
   python -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   ```

5. Llenar `data/seed.csv` con las academias que ya conoces:

   ```csv
   name,url,instagram,comuna
   Academia Ejemplo,https://ejemplo.cl,@ejemplo,Providencia
   ```

   `url` e `instagram` son opcionales; una academia solo con Instagram se
   publica igual, como no verificada.

## Uso

```bash
# Descubrir y generar propuestas sin tocar la base
bailoteca run --dry-run

# Igual, escribiendo propuestas en Postgres
bailoteca run

# Ver propuestas pendientes en Markdown
bailoteca review

# Aprobar una propuesta (fija verified_at)
bailoteca approve <proposal-id>

# Aprobar una ficha incompleta sin darla por verificada
bailoteca approve <proposal-id> --unverified

# Corregir y aprobar (abre $EDITOR con el payload JSON)
bailoteca edit <proposal-id>

# Descartar una propuesta
bailoteca reject <proposal-id>

# Agregar una academia a mano: @handle, URL o nombre
bailoteca add "@academia_ejemplo"

# Releer una academia publicada y proponer solo diferencias
bailoteca refresh academia-ejemplo

# Exportar lo publicado
bailoteca export
bailoteca export --csv
```

Cada corrida escribe `reports/<fecha>/` con `candidates.json`,
`proposals.json`, `review.md` y `summary.md`.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Los tests de integración se saltan si no hay `TEST_DATABASE_URL`. Para
correrlos contra un Postgres de prueba:

```bash
docker run -d --name bailoteca-test-db \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=bailoteca_test \
  -p 55432:5432 postgres:16-alpine

docker exec -i bailoteca-test-db psql -U postgres -d bailoteca_test \
  < supabase/migrations/0001_schema.sql
docker exec -i bailoteca-test-db psql -U postgres -d bailoteca_test \
  < supabase/migrations/0002_rls.sql

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/bailoteca_test \
  .venv/bin/python -m pytest -q
```

## Actualización mensual

`.github/workflows/weekly.yml` corre el **1° de cada mes a las 03:00 UTC**:

1. instala dependencias,
2. corre la suite,
3. ejecuta `bailoteca run` con los secretos del repositorio,
4. sube `reports/` como artifact.

Configurar en GitHub `Settings → Secrets and variables → Actions`:
`DATABASE_URL`, `GEMINI_API_KEY` y `SERPAPI_KEY` (esta última es la
**recomendada** para descubrimiento web).

Fuentes (`BAILOTECA_SOURCES`):

- `seed,serpapi` (recomendado): CSV curado + Google Search vía SerpApi.
- `seed,search`: CSV + DuckDuckGo HTML. **DDG suele bloquear** con una página
  `anomaly.js` (status 202) en IPs datacenter; solo como respaldo manual.
- `seed,search,osm`: además OSM, desactivado por defecto.

> Nota de cuota: SerpApi free = ~250 req/mes. La corrida mensual completa
> (10 comunas × 4 variantes = 40 queries) queda muy bajo el límite.

La corrida mensual **no vuelve a descargar** las academias publicadas; solo
comprueba enlaces. Para releer una ficha concreta, usar `bailoteca refresh <slug>`.

### OSM

`OverpassSource` está implementado pero desactivado por defecto. El spike del
2026-11-09 no pudo medir su cobertura porque la red bloqueó ambos endpoints; ver
`docs/osm-spike.md`. Se puede activar con `BAILOTECA_SOURCES=seed,search,osm`
cuando haya red y se valide el criterio de corte.

## Seguridad

- RLS activo en las ocho tablas.
- La llave anónima solo hace `select` sobre `styles`, `academies`,
  `academy_locations`, `academy_links` y `academy_styles`.
- No hay políticas de escritura para `anon`.
- `candidates`, `proposals` y `field_rejections` solo se leen y escriben con la
  llave de servicio (la CLI).
- No se scrapea Instagram: se guarda el handle público como enlace.
- El HTML crudo queda en `data/cache/` (ignorado por git) y como artifact del
  workflow, nunca en la base.

## Estructura

```text
src/bailoteca/
  cli.py        # comandos bailoteca
  config.py     # lectura de entorno
  db.py         # SQL y conexión (sin commit; la CLI cierra)
  discover.py   # deduplicación entre fuentes
  enrich.py     # descarga segura, JSON-LD, redes y caché
  classify.py   # reglas + fusión con LLM
  propose.py    # payloads, dedupe y rechazos
  publish.py    # validación, aprobación y publicación
  run.py        # corrida completa, dry-run y refresh
  links.py      # enlaces muertos
  report.py     # reporte semanal
  osm_spike.py  # resumen de cobertura OSM
supabase/migrations/
tests/
data/seed.csv
```

## Limitaciones de v1

- Sin horarios ni precios.
- Sin frontend: se lee por la REST automática de Supabase.
- Solo comunas de Santiago en las consultas de búsqueda.
- `verified_at` solo lo fija una persona; una corrida automática nunca lo toca.