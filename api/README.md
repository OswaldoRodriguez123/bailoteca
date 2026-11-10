# Bailoteca API

API pública de solo lectura para el directorio de academias de Bailoteca. La
consume la web Angular; no expone escrituras ni credenciales.

## Stack

- **FastAPI** + **Uvicorn**.
- **`slowapi`** para el rate limit por IP, con storage en memoria.
- **`bailoteca-shared`** para la conexión, las consultas y los DTOs
  (`Academy`, `AcademyLocation`, `AcademyLink`, `AcademyStyle`).
- Postgres de Supabase con el usuario **read-only** `bailoteca_api`.

> FastAPI queda pinneado a `<0.137`: desde 0.137 los routers incluidos se
> anidan y `slowapi` 0.1.10 deja de encontrar el handler, por lo que su
> middleware **salta el límite en silencio**. El pin está en
> `pyproject.toml`.

## Estructura

```text
api/
├── pyproject.toml
├── requirements.txt            # instalación local con pip
├── .env.example
├── bailoteca_api/
│   ├── main.py                 # create_app: CORS, limiter, routers, errores
│   ├── config.py               # Settings desde env
│   ├── db.py                   # pool perezoso + dependency get_conn
│   ├── rate_limit.py           # limiter por IP + handler 429
│   ├── schemas.py              # AcademyPage, StyleList, ComunaList
│   └── routers/
│       ├── health.py
│       └── academies.py
└── tests/
```

## Instalación

Desde la raíz del repo:

```bash
python -m venv .venv
.venv/bin/pip install -e shared -e "api[dev]"
```

## Cómo correrla

```bash
# desde la raíz
cp api/.env.example api/.env      # completar DATABASE_URL_READONLY
.venv/bin/uvicorn bailoteca_api.main:app --reload
```

- `/docs` y `/openapi.json` quedan disponibles en local.
- Sin `DATABASE_URL_READONLY`, la app arranca igual: `/health` y los endpoints
  de datos responden **503** en vez de romper el cold start.

## Tests

```bash
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m pytest shared/tests api/tests -q
```

Los tests no abren una base real: sobrescriben `get_conn` y monkeypatchean las
consultas de `bailoteca_shared`. Los tests de integración de `parser/` se
saltan si no hay `TEST_DATABASE_URL`.

## Endpoints

| Método | Ruta                | Respuesta                                    |
| ------ | ------------------- | -------------------------------------------- |
| `GET`  | `/health`           | `{"status": "ok", "database": "ok"}` o 503   |
| `GET`  | `/academies`        | `AcademyPage`                                |
| `GET`  | `/academies/{slug}` | `Academy` o 404                              |
| `GET`  | `/styles`           | `{"items": [{"slug", "name", "sort"}]}`      |
| `GET`  | `/comunas`          | `{"items": ["Providencia", ...]}`            |

### `GET /academies`

| Parámetro   | Tipo   | Reglas                                                       |
| ----------- | ------ | ------------------------------------------------------------ |
| `comuna`    | string | Opcional, máx. 100, exacta sin distinguir mayúsculas         |
| `style`     | string | Opcional, slug `^[a-z0-9-]+$`                                |
| `q`         | string | Opcional, 2–100 caracteres, busca en nombre y descripción    |
| `page`      | int    | Default 1, mínimo 1                                          |
| `page_size` | int    | Default 20, mínimo 1, máximo 100                             |

- Los filtros vacíos (`?comuna=&style=&q=`) se tratan como ausentes.
- Orden fijo: `name asc`.
- Un `style` o `comuna` sin coincidencias devuelve `items: []`, no error.
- Una página fuera de rango devuelve `items: []` con el total real.

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

## Rate limit

- `RATE_LIMIT` usa la sintaxis de `limits`, por defecto `60/minute` por IP.
- La IP sale del primer valor de `X-Forwarded-For` (Vercel lo setea) o de
  `request.client.host` en local.
- Al pasarse devuelve **429** con
  `{"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."}` y header
  `Retry-After`.
- El storage es en memoria: en Vercel cada instancia cuenta por separado, así
  que el límite es aproximado. Para exactitud habría que cambiar el storage de
  `slowapi`, sin tocar los endpoints.

## Usuario read-only y RLS

`supabase/migrations/0002_rls.sql` habilita RLS y crea políticas solo para
`anon` (que es `nologin`). Un rol nuevo con `GRANT SELECT` pero sin políticas
propias leería cero filas. Por eso se aplica también:

```text
supabase/migrations/0003_api_readonly.sql
```

Esa migración crea el rol `bailoteca_api`, le da `select` solo sobre las cinco
tablas publicadas y agrega políticas de lectura. La contraseña **no** está en el
repo; se define a mano en el SQL Editor de Supabase:

```sql
alter role bailoteca_api with password '<password>';
```

Luego se arma `DATABASE_URL_READONLY` con ese rol y el connection string del
**pooler** de Supabase (puerto 6543). La API crea el pool con
`prepare_threshold=None` para no chocar con el pooler en modo transacción.

Comprobación manual después de aplicar la migración:

1. Con `bailoteca_api`, `select count(*) from academies` devuelve filas (no cero
   por RLS).
2. Un `insert` falla por permisos.
3. `/health`, `/academies` con cada filtro, detalle, `/styles` y `/comunas`
   responden.

## Variables de entorno

| Variable                | Default                 | Uso                                   |
| ----------------------- | ----------------------- | ------------------------------------- |
| `DATABASE_URL_READONLY` | vacío                   | Conexión de solo lectura a Supabase   |
| `CORS_ORIGINS`          | `http://localhost:4200` | Orígenes separados por coma           |
| `RATE_LIMIT`            | `60/minute`             | Límite por IP                         |
| `DB_POOL_MAX_SIZE`      | `4`                     | Conexiones máximas del pool           |

`CORS_ORIGINS=*` permite cualquier origen; es aceptable para una API pública de
solo lectura, pero en producción conviene listar el dominio de la web.

## Errores

- Base de datos no configurada, caída o inalcanzable → **503**
  `{"detail": "Base de datos no disponible"}`.
- Excepción no controlada → **500** `{"detail": "Error interno"}`.
- Validación de parámetros → **422**.
- Nunca se devuelve el mensaje de psycopg ni un stack trace.

## Despliegue en Vercel

- **Root Directory**: `api/`.
- Vercel resuelve `[tool.vercel] entrypoint = "bailoteca_api.main:app"` como
  `api/bailoteca_api/main.py`. Por eso el paquete vive en la raíz de `api/`, no
  dentro de `src/`.
- Vercel instala desde `pyproject.toml` con `uv`, no desde `requirements.txt`.
  Por eso `bailoteca-shared` está declarado en `[project].dependencies` y
  resuelto desde `../shared` con `[tool.uv.sources]`.
- `requirements.txt` queda para instalaciones locales con pip; también usa el
  paquete local y `../shared`, sin `-e`.
- Si el build de Vercel no ve `../shared`, la salida documentada es usar una
  dependencia `git+https://...#subdirectory=shared` en `pyproject.toml`.
- Configurar `DATABASE_URL_READONLY`, `CORS_ORIGINS`, `RATE_LIMIT` y
  `DB_POOL_MAX_SIZE` en Vercel. Ningún `.env` se versiona.

## CI

`.github/workflows/api.yml` corre en `push` y `pull_request` que toquen
`api/**` o `shared/**`:

```bash
pip install -e shared -e "api[dev]"
python -m pytest shared/tests api/tests -q
```
