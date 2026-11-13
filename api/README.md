# Bailoteca API

Public read-only API for the Bailoteca academy directory. It is consumed by the
Angular web app; it exposes no writes and no credentials.

## Stack

- **FastAPI** + **Uvicorn**.
- **`slowapi`** for per-IP rate limiting, with in-memory storage.
- **`bailoteca-shared`** for the connection, the queries and the DTOs
  (`Academy`, `AcademyLocation`, `AcademyLink`, `AcademyStyle`).
- Supabase Postgres with the **read-only** user `bailoteca_api`.

> FastAPI is pinned to `<0.137`: from 0.137 on, included routers are nested and
> `slowapi` 0.1.10 can no longer find the handler, so its middleware **silently
> skips the limit**. The pin lives in `pyproject.toml`.

## Structure

```text
api/
├── pyproject.toml
├── requirements.txt            # local install with pip
├── .env.example
├── bailoteca_api/
│   ├── main.py                 # create_app: CORS, limiter, routers, errors
│   ├── config.py               # Settings from env
│   ├── db.py                   # lazy pool + get_conn dependency
│   ├── rate_limit.py           # per-IP limiter + 429 handler
│   ├── schemas.py              # AcademyPage, StyleOption, StyleList, ComunaList
│   └── routers/
│       ├── health.py
│       └── academies.py
└── tests/
```

## Install

From the repo root:

```bash
python -m venv .venv
.venv/bin/pip install -e shared -e "api[dev]"
```

## Running it

```bash
# from the repo root
cp api/.env.example api/.env      # fill in DATABASE_URL_READONLY
.venv/bin/uvicorn bailoteca_api.main:app --reload
```

- `/docs` and `/openapi.json` are available locally.
- Without `DATABASE_URL_READONLY` the app still starts: `/health` and the data
  endpoints answer **503** instead of breaking the cold start.

## Tests

```bash
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m pytest shared/tests api/tests -q
```

The tests do not open a real database: they override `get_conn` and monkeypatch
the `bailoteca_shared` queries. The `parser/` integration tests are skipped when
`TEST_DATABASE_URL` is missing.

## Endpoints

| Method | Route               | Response                                     |
| ------ | ------------------- | -------------------------------------------- |
| `GET`  | `/health`           | `{"status": "ok", "database": "ok"}` or 503  |
| `GET`  | `/academies`        | `AcademyPage`                                |
| `GET`  | `/academies/{slug}` | `Academy` or 404                             |
| `GET`  | `/styles`           | `{"items": [{"slug", "name", "sort"}]}`      |
| `GET`  | `/comunas`          | `{"items": ["Providencia", ...]}`            |

### `GET /academies`

| Parameter   | Type   | Rules                                                        |
| ----------- | ------ | ------------------------------------------------------------ |
| `comuna`    | string | Optional, max. 100, exact, case-insensitive                  |
| `style`     | string | Optional, slug `^[a-z0-9-]+$`                                |
| `q`         | string | Optional, 2–100 characters, searches name and description    |
| `page`      | int    | Default 1, minimum 1                                         |
| `page_size` | int    | Default 20, minimum 1, maximum 100                           |

- Empty filters (`?comuna=&style=&q=`) are treated as absent.
- Fixed order: `name asc`.
- A `style` or `comuna` with no matches returns `items: []`, not an error.
- A page out of range returns `items: []` with the real total.

Response:

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

- `RATE_LIMIT` uses the `limits` syntax, `60/minute` per IP by default. The
  budget is aggregate across all routes (slowapi `application_limits`), not
  per endpoint.
- The IP key comes from `x-vercel-forwarded-for` (Vercel sets it and does not
  forward client-supplied values; it is also kept when Vercel sits behind an
  upstream proxy), falling back to `x-real-ip`, then to the rightmost
  `X-Forwarded-For` hop (what the outermost appending proxy observed), then
  to `request.client.host` locally. The leftmost XFF hop is client-controlled
  and is never used as the key.
- Trust assumption: the API is served on Vercel (or behind a proxy that
  overwrites/appends `X-Forwarded-For`). Exposed directly to the internet
  with no proxy, `X-Forwarded-For` is fully client-controlled; put a proxy in
  front or the limiter can be bypassed by rotating the header.
- Going over returns **429** with
  `{"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."}` and a
  `Retry-After` header.
- Storage is in memory: on Vercel each instance counts separately, so the limit
  is approximate. For exactness you would change the `slowapi` storage, without
  touching the endpoints.

## Read-only user and RLS

`supabase/migrations/0002_rls.sql` enables RLS and creates policies only for
`anon` (which is `nologin`). A new role with `GRANT SELECT` but no policies of
its own would read zero rows. That is why this is applied too:

```text
supabase/migrations/0003_api_readonly.sql
```

That migration creates the `bailoteca_api` role, grants `select` only on the
five published tables and adds read policies. The password is **not** in the
repo; it is set by hand in the Supabase SQL Editor:

```sql
alter role bailoteca_api with password '<password>';
```

Then `DATABASE_URL_READONLY` is built with that role and the Supabase **pooler**
connection string (port 6543). The API creates the pool with
`prepare_threshold=None` to avoid clashing with the pooler in transaction mode.

Manual check after applying the migration:

1. As `bailoteca_api`, `select count(*) from academies` returns rows (not zero
   because of RLS).
2. An `insert` fails on permissions.
3. `/health`, `/academies` with each filter, the detail, `/styles` and
   `/comunas` respond.

## Environment variables

| Variable                | Default                 | Use                                   |
| ----------------------- | ----------------------- | ------------------------------------- |
| `DATABASE_URL_READONLY` | empty                   | Read-only connection to Supabase      |
| `CORS_ORIGINS`          | `http://localhost:4200` | Comma-separated origins               |
| `RATE_LIMIT`            | `60/minute`             | Per-IP limit                          |
| `DB_POOL_MAX_SIZE`      | `4`                     | Maximum pool connections              |

`CORS_ORIGINS=*` allows any origin; it is acceptable for a public read-only API,
but in production it is better to list the web domain.

## Errors

- Database not configured, down or unreachable → **503**
  `{"detail": "Base de datos no disponible"}`.
- Unhandled exception → **500** `{"detail": "Error interno"}`.
- Parameter validation → **422**.
- The psycopg message or a stack trace is never returned.

## Deploying to Vercel

- **Root Directory**: `api/`.
- Vercel resolves `[tool.vercel] entrypoint = "bailoteca_api.main:app"` as
  `api/bailoteca_api/main.py`. That is why the package lives at the root of
  `api/`, not inside `src/`.
- Vercel installs from `pyproject.toml` with `uv`, not from `requirements.txt`.
  That is why `bailoteca-shared` is declared in `[project].dependencies` and
  resolved from `../shared` with `[tool.uv.sources]`.
- `requirements.txt` is kept for local pip installs; it also uses the local
  package and `../shared`, without `-e`.
- If the Vercel build cannot see `../shared`, the documented workaround is a
  `git+https://...#subdirectory=shared` dependency in `pyproject.toml`.
- Configure `DATABASE_URL_READONLY`, `CORS_ORIGINS`, `RATE_LIMIT` and
  `DB_POOL_MAX_SIZE` in Vercel. No `.env` is versioned.

## CI

`.github/workflows/api.yml` runs on `push` and `pull_request` that touch
`api/**` or `shared/**`:

```bash
pip install -e shared -e "api[dev]"
python -m pytest shared/tests api/tests -q
```
