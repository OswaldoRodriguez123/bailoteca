# Bailoteca

Dance school directory for Chile. A monorepo with a data pipeline, a
read-only API and a web app, all on one shared Postgres schema.

[![API](https://github.com/OswaldoRodriguez123/bailoteca/actions/workflows/api.yml/badge.svg)](https://github.com/OswaldoRodriguez123/bailoteca/actions/workflows/api.yml)
[![web](https://github.com/OswaldoRodriguez123/bailoteca/actions/workflows/web.yml/badge.svg)](https://github.com/OswaldoRodriguez123/bailoteca/actions/workflows/web.yml)
[![parser](https://github.com/OswaldoRodriguez123/bailoteca/actions/workflows/parser.yml/badge.svg)](https://github.com/OswaldoRodriguez123/bailoteca/actions/workflows/parser.yml)

[Web](https://bailoteca.vercel.app) · [API docs](https://bailoteca-api.vercel.app/docs)

![Bailoteca web app](docs/assets/screenshot.png)

- **$0 to run**: Supabase free tier, GitHub Actions and free data sources.
- **Published means a human approved it**: the pipeline proposes, the CLI publishes.
- **No Instagram scraping**: only the public profile preview (Open Graph) is
  read; it never logs in or walks through posts.

## How it works

```text
discover → filter → enrich → classify → propose → approve
```

1. **Discover** academies from a seed list, web search and OpenStreetMap.
2. **Filter** noise (directories, aggregators, unrelated results).
3. **Enrich** with the public site, JSON-LD, social links and Google Maps.
4. **Classify** dance styles with rules plus an LLM fallback.
5. **Propose** a payload for a human to review.
6. **Approve** with the CLI, which validates and publishes to Postgres.

## Components

| Folder | What it is | Status |
| --- | --- | --- |
| `parser/` | Pipeline: discover → filter → enrich → classify → propose | Working |
| `shared/` | `bailoteca-shared` package: connection, reads and Pydantic DTOs | Working |
| `api/` | Read-only FastAPI | Working |
| `web/` | Angular: list and detail views | Working |
| `supabase/migrations/` | Shared schema and RLS | Working |

```text
bailoteca/
├── parser/                  # pipeline + CLI
│   ├── src/bailoteca/
│   ├── tests/
│   ├── data/                # seed.csv + cache (ignored)
│   └── reports/             # per-run reports (ignored)
├── shared/                  # bailoteca-shared
│   ├── src/bailoteca_shared/
│   └── tests/
├── api/                     # FastAPI
├── web/                     # Angular SPA
├── supabase/migrations/     # schema, RLS, read-only role and data migrations
├── docs/architecture.md     # design decisions
└── .github/workflows/       # parser.yml, api.yml, web.yml
```

## Parser quickstart

Requirements: Python 3.12+, a Postgres 14+ database (Supabase free works) and,
optionally, a Gemini API key.

```bash
# 1. Environment and install (from the repo root)
python -m venv .venv
.venv/bin/pip install -e shared -e "parser[dev]"

# 2. Configuration
cp parser/.env.example parser/.env
# edit parser/.env with DATABASE_URL and the optional keys

# 3. Migrations (Supabase SQL Editor, in order)
#    apply every file in supabase/migrations/, from 0001 to the latest

# 4. Run the pipeline
cd parser
../.venv/bin/python -m bailoteca run --dry-run   # no database writes
../.venv/bin/python -m bailoteca run             # writes proposals
../.venv/bin/python -m bailoteca review          # list pending
../.venv/bin/python -m bailoteca approve <id>    # publish
```

Pipeline details, noise filter, sources and SerpApi quota live in
[`parser/README.md`](parser/README.md).

## Tests

```bash
# from the repo root
.venv/bin/python -m pytest parser/tests shared/tests -q
.venv/bin/python -m pytest shared/tests api/tests -q

# integration against a test Postgres
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/bailoteca_test \
  .venv/bin/python -m pytest parser/tests shared/tests -q

# web
cd web && npm test -- --watch=false
```

## API and web

- [`api/README.md`](api/README.md): read-only FastAPI, endpoints, filters,
  rate limit and the read-only database user.
- [`web/README.md`](web/README.md): Angular app and `API_BASE_URL`.

```bash
.venv/bin/pip install -e shared -e "api[dev]"
cp api/.env.example api/.env      # fill in DATABASE_URL_READONLY
.venv/bin/uvicorn bailoteca_api.main:app --reload
```

## Deployment

- **Parser**: GitHub Actions, `.github/workflows/parser.yml`, on the **1st of
  each month at 03:00 UTC**. It only runs on schedule or manually
  (`workflow_dispatch`); a push does not trigger it.
- **API**: Vercel with Root Directory `api/`:
  <https://bailoteca-api.vercel.app> (`/docs` for OpenAPI).
- **Web**: Vercel with Root Directory `web/`:
  <https://bailoteca.vercel.app>.
- **Database**: Supabase; migrations are applied by hand from the SQL Editor.

## Secrets

No `.env` is committed. Each component has its own `.env.example`:

| Component | Variables |
| --- | --- |
| Parser | `DATABASE_URL` (write), `GEMINI_API_KEY`, `SERPAPI_KEY`, `BRAVE_API_KEY`, `CLOUDFLARE_*` |
| API | `DATABASE_URL_READONLY`, `CORS_ORIGINS`, `RATE_LIMIT`, `DB_POOL_MAX_SIZE` |
| Web | `API_BASE_URL` |

In GitHub Actions the parser secrets live in
`Settings → Secrets and variables → Actions`. The API uses the Supabase user
`bailoteca_api`, created by `supabase/migrations/0003_api_readonly.sql`; its
password is set by hand in the SQL Editor and passed as
`DATABASE_URL_READONLY` (pooler, port 6543).

## Documentation

- [Architecture and design decisions](docs/architecture.md)
- [OSM spike notes](parser/docs/osm-spike.md)

## License

MIT. See [LICENSE](LICENSE).
