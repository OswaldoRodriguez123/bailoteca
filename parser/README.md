# Bailoteca Parser

**Bailoteca Parser** es el pipeline de un directorio de academias de baile en
Santiago, empezando por salsa. Descubre candidatos desde fuentes gratuitas, los
clasifica por estilo con evidencia y deja propuestas para que una persona las
apruebe antes de publicarlas.

Este paquete vive en `parser/` dentro del monorepo. La conexión y las consultas
de lectura vienen de `shared/` (`bailoteca-shared`); el parser conserva las
escrituras y la CLI.

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
   publicadas. Las migraciones viven en la raíz del repo porque el esquema es
   compartido con la API.

3. Copiar `.env.example` a `.env` y llenar los valores:

   ```bash
   cp .env.example .env
   ```

   `DATABASE_URL` es un secreto: no se versiona ni se pega en el chat. La llave
   anónima de Supabase sirve para leer desde el frontend, nunca para escribir.

4. Instalar los paquetes desde la raíz del repo:

   ```bash
   python -m venv .venv
   .venv/bin/pip install -e shared -e "parser[dev]"
   ```

   `bailoteca-shared` debe instalarse antes o junto con el parser; sin él los
   imports de lectura fallan.

5. Llenar `data/seed.csv` con las academias que ya conoces:

   ```csv
   name,url,instagram,comuna
   Academia Ejemplo,https://ejemplo.cl,@ejemplo,Providencia
   ```

   `url` e `instagram` son opcionales; una academia solo con Instagram se
   publica igual, como no verificada.

## Uso

Todos los comandos se ejecutan desde `parser/` con el virtualenv activado
(`source ../.venv/bin/activate`):

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

Desde la raíz del repo:

```bash
.venv/bin/python -m pytest parser/tests shared/tests -q
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
  .venv/bin/python -m pytest parser/tests shared/tests -q
```

## Actualización mensual

`.github/workflows/parser.yml` corre el **1° de cada mes a las 03:00 UTC**:

1. instala dependencias (`shared` + `parser`),
2. corre la suite,
3. ejecuta `bailoteca run` con los secretos del repositorio,
4. sube `parser/reports/` como artifact.

El workflow solo se dispara con cambios en `parser/**`, `shared/**` o el propio
YAML.

Configurar en GitHub `Settings → Secrets and variables → Actions`:
`DATABASE_URL`, `GEMINI_API_KEY` y `SERPAPI_KEY` (esta última es la
**recomendada** para descubrimiento web). Opcionalmente
`CLOUDFLARE_ACCOUNT_ID` y `CLOUDFLARE_API_TOKEN` para el triaje de ruido.

### Filtro de ruido

Cada corrida pasa por dos etapas antes de crear propuestas:

```text
descubrir → reglas deterministas → enriquecer → Clef → propuestas
```

1. **Reglas** (`bailoteca/sources/filters.py`): descartan directorios
   (`superprof.cl`, `salirsantiago.com`, `2x3.cl`…), posts/videos/eventos de
   redes y páginas `/popular/` de Instagram. Conservan perfiles y homepages de
   grupos de Facebook.
2. **Clef** (`@cf/cloudflare/clef-flash`): juzga con ~600 caracteres del texto
   real de la página si es una academia que enseña salsa/bachata en la Región
   Metropolitana. Umbral `min(academia, salsa, santiago) >= 0.5`.

Los descartes **no se guardan** en la base: se vuelven a descubrir y juzgar el
mes siguiente. Si faltan las credenciales de Cloudflare o Clef falla, el
candidato pasa (**fail-open**), para no perder academias reales. Los contadores
`filtrados_reglas`, `filtrados_clef` y `clef_errors` aparecen en el log y en
`summary.md`.

Fuentes (`BAILOTECA_SOURCES`):

- `seed,serpapi` (recomendado): CSV curado + Google Search vía SerpApi.
- `seed,search`: CSV + DuckDuckGo HTML. **DDG suele bloquear** con una página
  `anomaly.js` (status 202) en IPs datacenter; solo como respaldo manual.
- `seed,search,osm`: además OSM, desactivado por defecto.

> Nota de cuota: SerpApi free = ~250 req/mes. La corrida mensual completa
> (10 comunas × 4 variantes = 40 queries) queda muy bajo el límite.
>
> Las respuestas de SerpApi se cachean en `data/cache/serpapi/` con **TTL de
> 24 h**, por consulta y sin incluir `api_key` en la clave. Repetir una corrida
> el mismo día no gasta búsquedas; el cron mensual siempre refresca. Si el
> archivo de caché está corrupto o no se puede escribir, se ignora y se vuelve
> a consultar la API. En GitHub Actions `data/cache/serpapi` se restaura con
> `actions/cache`, así que re-ejecutar el workflow el mismo día tampoco gasta
> búsquedas; el cron mensual siempre encuentra la caché vencida.

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
parser/
  src/bailoteca/
    cli.py        # comandos bailoteca
    config.py     # lectura de entorno
    db.py         # escrituras SQL; reexporta las lecturas de shared
    discover.py   # deduplicación entre fuentes
    enrich.py     # descarga segura, JSON-LD, redes y caché
    classify.py   # reglas + fusión con LLM
    propose.py    # payloads, dedupe y rechazos
    publish.py    # validación, aprobación y publicación
    run.py        # corrida completa, dry-run y refresh
    links.py      # enlaces muertos
    report.py     # reporte semanal
    osm_spike.py  # resumen de cobertura OSM
  tests/
  data/seed.csv
  reports/
shared/           # conexión, lecturas y DTOs compartidos con la API
supabase/migrations/
```

## Limitaciones de v1

- Sin horarios ni precios.
- Sin frontend todavía: la API y la web están planificadas en `api/` y `web/`.
- Solo comunas de Santiago en las consultas de búsqueda.
- `verified_at` solo lo fija una persona; una corrida automática nunca lo toca.