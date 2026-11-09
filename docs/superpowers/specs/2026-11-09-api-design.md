# Diseño: API pública de Bailoteca

**Fecha:** 2026-11-09
**Estado:** propuesto (pendiente de aprobación)
**Decisión previa:** filtros en SQL (A) + rate limit con `slowapi` en memoria (B).

## Intención

Implementar `api/` con FastAPI de solo lectura para que la web Angular muestre
las academias publicadas. La API debe permitir filtrar y paginar, reusar el
contrato de `bailoteca-shared` y resistir abuso básico con un rate limit por IP.

El directorio es chico y el tráfico esperado es bajo. La prioridad es claridad,
pocas dependencias y que el código se pueda leer como parte del portafolio.

## Objetivos

- Implementar `GET /health`, `GET /academies`, `GET /academies/{slug}`,
  `GET /styles` y `GET /comunas`.
- Filtrar por `comuna`, `style` y texto libre `q`; paginar con `page` y
  `page_size`.
- Reusar `bailoteca_shared` para conexión y DTOs. La API no define su propio
  modelo de academia.
- Rate limit por IP con `slowapi` y storage en memoria, configurable por env.
- CORS configurable para la web Angular.
- Tests de API sin base de datos real, más tests unitarios del armado de filtros.
- Dejar la app lista para correr en local y documentar el despliegue en Vercel.
- Agregar la migración y las políticas RLS para el usuario read-only de la API.
- Agregar un workflow de CI mínimo para `api/**` y `shared/**`.

## No objetivos

- Escrituras, administración, autenticación o API keys.
- Rate limit distribuido (Redis/Upstash) o exacto entre instancias.
- Búsqueda full-text, ordenamiento configurable, paginación por cursor.
- Búsqueda insensible a acentos.
- Implementar la web Angular.
- Tocar el comportamiento del parser o del pipeline.

## Anti-objetivos

- Duplicar el SQL o los DTOs de `shared` dentro de la API.
- Usar `DATABASE_URL` de escritura en la API.
- Traer todas las academias en cada request para filtrar en Python.
- Agregar Redis, Upstash o un servicio externo solo para el rate limit.
- Exponer stack traces, errores de psycopg o detalles internos al cliente.
- Versionar `.env` o secretos.

## Enfoques considerados

### Filtros y paginación

1. **SQL en `shared` (elegido).** Una función `list_academies` arma `where` con
   parámetros y devuelve la página y el total. No carga filas que no se van a
   mostrar y el rate limit protege una consulta acotada.
2. **Filtrar en Python sobre `list_published`.** Descartado: cada request
   cargaría todas las academias y sus relaciones. Funciona con pocos datos, pero
   es justo lo que un rate limit debería evitar y no escala.

### Rate limit

1. **`slowapi` con storage en memoria (elegido).** Es la librería estándar para
   FastAPI, evita escribir un middleware propio y se configura con una línea.
   Limitación conocida: en Vercel cada instancia tiene su contador, así que el
   límite es aproximado.
2. **Middleware propio en memoria.** Descartado: menos dependencias, pero más
   código propio que mantener y probar para el mismo resultado.
3. **Upstash Redis.** Descartado: contador exacto entre instancias, pero suma un
   servicio, secretos y configuración. Sobreingeniería para este caso.

## Diseño

### Estructura

```text
api/
├── pyproject.toml              # fastapi, uvicorn, slowapi, psycopg[pool], pydantic-settings
├── requirements.txt            # instalación para Vercel
├── vercel.json                 # rewrite a index.py
├── index.py                    # reexporta app para Vercel
├── .env.example
├── README.md
├── src/bailoteca_api/
│   ├── __init__.py
│   ├── main.py                 # create_app: CORS, limiter, routers, handlers
│   ├── config.py               # Settings desde env
│   ├── db.py                   # pool perezoso + dependency get_conn
│   ├── rate_limit.py           # limiter, key por IP, handler 429
│   ├── schemas.py              # AcademyPage, StyleOption (reusan Academy)
│   └── routers/
│       ├── __init__.py
│       ├── health.py
│       └── academies.py
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_academies.py
    └── test_rate_limit.py
```

También se agregan, fuera de `api/`:

```text
supabase/migrations/0003_api_readonly.sql   # rol, grants y políticas RLS
.github/workflows/api.yml                   # pytest con paths api/** y shared/**
```

### Dependencias

- `fastapi`, `uvicorn[standard]`, `slowapi`, `psycopg[binary,pool]`,
  `pydantic-settings`, `bailoteca-shared` (editable en local).
- `dev`: `pytest`, `httpx` (lo usa `TestClient`).

Instalación local desde la raíz:

```bash
.venv/bin/pip install -e shared -e "api[dev]"
```

### Configuración

`config.py` usa `pydantic-settings` y lee `.env`:

| Variable                | Default                 | Uso                                      |
| ----------------------- | ----------------------- | ---------------------------------------- |
| `DATABASE_URL_READONLY` | vacío                   | Conexión de solo lectura a Supabase      |
| `CORS_ORIGINS`          | `http://localhost:4200` | Orígenes separados por coma              |
| `RATE_LIMIT`            | `60/minute`             | Límite por IP en sintaxis de `limits`    |
| `DB_POOL_MAX_SIZE`      | `4`                     | Conexiones máximas del pool              |

Si `DATABASE_URL_READONLY` falta, la app arranca igual: `/health` responde 503
y los endpoints de datos devuelven 503. Esto evita que un cold start de Vercel
explote por configuración y hace visible el problema sin filtrar detalles.

`get_settings()` se cachea con `lru_cache`; los tests lo sobrescriben.

### Conexión a base de datos

- `psycopg_pool.ConnectionPool` creado de forma perezosa la primera vez que se
  usa, con `min_size=0`, `max_size=DB_POOL_MAX_SIZE`, `timeout=5`,
  `max_idle=60`, `row_factory=dict_row` y `prepare_threshold=None`.
- `prepare_threshold=None` evita prepared statements, que chocan con el pooler
  de Supabase en modo transacción.
- Dependency `get_conn()` toma una conexión del pool y la devuelve al terminar.
- Usar el connection string **pooler** de Supabase (puerto 6543) en producción.
- Los tests sobrescriben `get_conn`; nunca abren una conexión real.

### Usuario read-only y RLS

`0002_rls.sql` habilita RLS en todas las tablas y solo crea políticas `to anon`,
que es un rol `nologin`. Un rol nuevo con `GRANT SELECT` pero sin políticas
propias leería cero filas, y usar el rol `postgres` rompería la promesa de
solo lectura. Por eso este cambio incluye `supabase/migrations/0003_api_readonly.sql`:

- Crea el rol `bailoteca_api` como `login` **sin contraseña** si no existe.
- Le da `usage` en `public` y `select` solo sobre `styles`, `academies`,
  `academy_locations`, `academy_links` y `academy_styles`.
- Agrega políticas de lectura `to bailoteca_api` en esas cinco tablas.
- No toca `candidates`, `proposals` ni `field_rejections`: quedan sin acceso.

La contraseña se define a mano en el SQL Editor de Supabase, nunca en una
migración ni en el repo:

```sql
alter role bailoteca_api with password '<password>';
```

Luego se arma `DATABASE_URL_READONLY` con ese rol y el host/puerto del pooler
que muestre Supabase. Esto queda documentado en `api/README.md`. Los tests
mocked no detectan un RLS mal configurado; la verificación real contra Supabase
es manual y se describe en la sección de verificación.

### Endpoints

| Método | Ruta                | Respuesta                                        |
| ------ | ------------------- | ------------------------------------------------ |
| `GET`  | `/health`           | `{"status": "ok", "database": "ok"}` o 503       |
| `GET`  | `/academies`        | `AcademyPage`                                    |
| `GET`  | `/academies/{slug}` | `Academy` o 404                                  |
| `GET`  | `/styles`           | `{"items": [{"slug", "name", "sort"}]}`          |
| `GET`  | `/comunas`          | `{"items": ["Providencia", ...]}`                |

#### `GET /academies`

Parámetros de query:

| Parámetro   | Tipo   | Reglas                                      |
| ----------- | ------ | ------------------------------------------- |
| `comuna`    | string | Opcional, máx. 100, comparación exacta sin distinguir mayúsculas |
| `style`     | string | Opcional, slug `^[a-z0-9-]+$`               |
| `q`         | string | Opcional, 2–100 caracteres, busca en nombre y descripción con `ilike` |

Los tres filtros se limpian con `strip()` antes de validar. Un valor vacío o
solo espacios se trata como ausente, porque los selects de Angular suelen
mandar `?comuna=` para "todos". `q` de un carácter después del `strip()` sí es
422. `style` se valida con el regex solo cuando queda un valor no vacío.
| `page`      | int    | Default 1, mínimo 1                         |
| `page_size` | int    | Default 20, mínimo 1, máximo 100            |

Respuesta:

```json
{
  "items": [
    {
      "id": "uuid",
      "slug": "danson-academy",
      "name": "Dansón Academy",
      "status": "active",
      "locations": [],
      "links": [],
      "styles": []
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 42
}
```

- Orden fijo: `name asc`.
- Un `style` desconocido no es error: devuelve lista vacía.
- Un `comuna` sin coincidencias devuelve lista vacía.
- `q` vacío se ignora; `q` de un carácter devuelve 422.
- `page` fuera de rango devuelve una página vacía con el total real.

#### `GET /academies/{slug}`

- Devuelve `Academy` completo (sedes, enlaces y estilos).
- 404 con `{"detail": "Academia no encontrada"}` si no existe.
- Sin validación estricta de formato: el slug se pasa como parámetro SQL.

#### `GET /styles` y `GET /comunas`

- Existen para que Angular arme los selects sin derivar opciones del listado.
- `/styles` ordena por `sort`, luego `name`; solo estilos existentes.
- `/comunas` devuelve comunas distintas, no vacías, ordenadas alfabéticamente.

### Cambios en `bailoteca-shared`

Se agregan funciones de solo lectura, sin tocar `list_published`:

- `list_academies(conn, *, comuna=None, style=None, q=None, limit=20, offset=0)`
  → `(rows, total)`.
- `get_academy_by_slug(conn, slug)` → `dict | None`.
- `list_styles(conn)` → `list[dict]`.
- `list_comunas(conn)` → `list[str]`.

Para no duplicar el `select` gigante de `list_published`, se extrae un helper
privado con las columnas y los `json_agg`. `list_published` pasa a usarlo sin
filtros, conservando su salida actual.

El armado de `where` vive en una función pura
`_academy_filters(comuna, style, q) -> (sql, params)` para poder probarlo sin
base de datos. Todos los valores van parametrizados; nunca se interpola texto
del usuario en el SQL.

Filtros:

- `comuna`: `exists (select 1 from academy_locations al where al.academy_id = a.id and lower(al.comuna) = lower(%s))`.
- `style`: `exists (select 1 from academy_styles ast join styles s on s.id = ast.style_id where ast.academy_id = a.id and s.slug = %s)`.
- `q`: `(a.name ilike %s or coalesce(a.description, '') ilike %s)` con `%q%`.

El total se calcula con el mismo `where` sobre `academies`, sin los `json_agg`.

### Rate limit

- `slowapi.Limiter` con `key_func` propio: primer valor de `X-Forwarded-For`
  (Vercel lo setea) o `request.client.host` en local.
- `default_limits=[settings.rate_limit]` aplicado con `SlowAPIMiddleware` a
  todas las rutas, incluido `/health` y `/docs`.
- Storage `memory://`; sin dependencias externas.
- Respuesta 429 con `{"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."}`
  y header `Retry-After`.
- El límite por defecto es `60/minute` por IP; se cambia con `RATE_LIMIT`.
- Limitación documentada: en Vercel cada instancia cuenta por separado. Para el
  objetivo ("que no la revienten") es suficiente; si algún día se necesita
  exactitud, se cambia el storage de `slowapi` sin tocar los endpoints.

### CORS

- `CORSMiddleware` con los orígenes de `CORS_ORIGINS`.
- `allow_methods=["GET", "OPTIONS"]`, `allow_headers=["*"]`,
  `allow_credentials=False`.
- Si `CORS_ORIGINS=*`, se permite cualquier origen; documentado como opción para
  una API pública de solo lectura.

### Errores

- `psycopg.OperationalError` y `psycopg.InterfaceError` → 503
  `{"detail": "Base de datos no disponible"}`.
- Cualquier excepción no controlada → 500 `{"detail": "Error interno"}`, con
  `logger.exception` del lado del servidor.
- Los errores de validación de FastAPI se dejan como vienen (422).
- Nunca se devuelve el mensaje de psycopg ni el stack trace.

### Tests

Sin base de datos real:

- `shared`: tests unitarios de `_academy_filters` (cláusulas y parámetros) y del
  contrato de `Academy` que ya existe.
- `api`: `TestClient` con `get_conn` sobrescrito y las funciones de `shared`
  usadas por los routers monkeypatcheadas.
  - `/academies` arma el sobre con `items`, `page`, `page_size`, `total`.
  - Los filtros y la paginación se pasan a `list_academies` tal como llegan.
  - `page_size=101` y `q` de un carácter devuelven 422.
  - Slug inexistente devuelve 404.
  - `/styles` y `/comunas` devuelven la forma esperada.
- `api` rate limit: crear la app con `RATE_LIMIT="2/minute"`, hacer tres
  requests y verificar 429 + `Retry-After`. Resetear el limiter entre tests.
- `/health`: 200 cuando `check_db` funciona y 503 cuando falla.

Opcional, si existe `TEST_DATABASE_URL`: un test de integración de
`list_academies` con datos insertados y `rollback`, siguiendo el patrón de
`parser/tests/test_db.py`.

### CI

- `.github/workflows/api.yml` corre en `push` y `pull_request` con `paths:
  api/**`, `shared/**` y el propio workflow.
- Python 3.12, `pip install -e shared -e "api[dev]"`,
  `pytest shared/tests api/tests -q`.
- No necesita base de datos: los tests son mocked.
- No toca el workflow mensual del parser.

### Despliegue

- Vercel con **Root Directory** `api/`.
- `index.py` reexporta `app`; `vercel.json` reescribe todas las rutas a
  `/index`.
- `requirements.txt` instala el paquete local y `../shared` (`-e .`,
  `-e ../shared`).
- Si Vercel no expone `../shared` en el build, la alternativa documentada es
  publicar `bailoteca-shared` como wheel o mover el Root Directory a la raíz.
  Esto se valida al desplegar, no en este cambio.
- Variables en Vercel: `DATABASE_URL_READONLY`, `CORS_ORIGINS`, `RATE_LIMIT`,
  `DB_POOL_MAX_SIZE`.

### Documentación

- `api/README.md`: instalar, correr, tests, endpoints, filtros, rate limit,
  variables y despliegue.
- `README.md` raíz: marcar `api/` como implementada y actualizar el comando de
  instalación.
- `api/.env.example`: agregar `RATE_LIMIT` y `DB_POOL_MAX_SIZE`.

## Verificación

- `.venv/bin/python -m pytest shared/tests api/tests -q` en verde.
- `.venv/bin/python -m pytest parser/tests -q` sigue en verde (sin
  `TEST_DATABASE_URL` los de integración se saltan).
- `uvicorn bailoteca_api.main:app` levanta y `/docs` responde.
- Con `DATABASE_URL_READONLY` real: `/health`, `/academies` con cada filtro,
  paginación, detalle, `/styles` y `/comunas` responden.
- Sin `DATABASE_URL_READONLY`: `/health` y `/academies` devuelven 503, no 500.
- 61 requests seguidos con `RATE_LIMIT=60/minute` devuelven 429 en la 61.
- Con el rol `bailoteca_api` creado y su contraseña puesta a mano, una consulta
  directa devuelve filas (no cero por RLS) y no puede escribir.
- `pytest` local y el workflow `api.yml` en verde.
- `git status` sin `.env`, secretos ni artefactos generados.

## Riesgos

- **Rate limit aproximado en Vercel:** aceptado y documentado.
- **Pooler de Supabase:** si se usa la conexión directa, el pool puede agotar
  conexiones. Se documenta el puerto 6543 y `prepare_threshold=None`.
- **`../shared` en Vercel:** el build puede no verlo. Se documenta la salida
  (wheel o Root Directory raíz) y no se bloquea la implementación local.
- **`ilike` no ignora acentos:** "nunoa" no encuentra "Ñuñoa". Aceptado; el
  filtro por comuna se elige de un select, no se escribe a mano.
- **Cambios en `shared`:** `list_published` se refactoriza; los tests del parser
  y de `shared` cubren que la salida no cambie.
- **RLS y rol nuevo:** si se olvidan las políticas, la API devuelve listas
  vacías en vez de un error. La migración las incluye y la verificación real
  contra Supabase es explícita.
- **Contraseña del rol:** se define a mano en Supabase; si se filtra en un
  `.env` local, se rota. Nunca se versiona.

## Decisiones dejadas al builder

- Nombres exactos de archivos y funciones dentro de la estructura propuesta.
- Redacción de mensajes de error y docstrings.
- Si se agrega el test de integración opcional de `shared`.
- Formato exacto de `vercel.json` y `requirements.txt`, siempre que cumplan lo
  descrito.
