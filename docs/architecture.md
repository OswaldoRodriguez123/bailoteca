# Architecture

Bailoteca is a monorepo with four deployable pieces that share one Postgres
schema. The goal is that the pipeline and the API never duplicate the schema or
the read layer, and that the repo reads as a complete system.

```text
parser/  →  Supabase (Postgres)  →  api/  →  web/
   ↑              ↑
shared/  ─────────┘  (connection, reads, DTOs)
```

## Decisions

### One repo, four folders

`parser/`, `api/`, `web/` and `shared/` live in the same repository. Each has
its own dependencies, `.env.example` and CI workflow, and each deploys
independently (Vercel Root Directory for `api/` and `web/`). A separate repo per
component was rejected: it splits the history and forces multiple clones.

### `shared/` instead of duplicated data access

`bailoteca-shared` holds the connection, the read queries and the Pydantic DTOs
used by both the parser and the API. Duplicating `db.py` or the models was
rejected because the schema would drift between components.

### Human approval before publishing

The pipeline only writes `candidates` and `proposals`. Publishing is a separate
CLI step (`bailoteca approve <id>`) that validates the payload and writes the
academy. This keeps bad scrapes out of the public directory and makes every
published record traceable to a review.

### Read-only API user

The API connects with a dedicated Supabase role created in
`0003_api_readonly.sql`. RLS is enabled on all tables, `anon` can only `select`
the public views, and there are no write policies for `anon`. `candidates`,
`proposals` and `field_rejections` are only reachable with the service key.

### No Instagram scraping

The parser stores the public handle as a link and reads only the public profile
preview (Open Graph tags) to get the display name and avatar. It never logs in,
paginates or walks through posts.

### Free-tier budget

The monthly run is designed around free quotas: SerpApi searches are cached in
`actions/cache`, the cron runs once a month, and the pipeline does not re-fetch
academies that are already published (it only re-checks links).

## Data flow

1. **Discover** — seed list, web search and OpenStreetMap (`OverpassSource`,
   implemented but disabled by default).
2. **Filter** — drop directories, aggregators and unrelated results.
3. **Enrich** — fetch the public site, JSON-LD, social links and Google Maps
   data; raw HTML stays in `data/cache/` (git-ignored).
4. **Classify** — rule-based dance styles with an LLM fallback.
5. **Propose** — build a payload, dedupe and record rejections.
6. **Approve** — validate and publish to Postgres.

## Migrations

Migrations are applied by hand from the Supabase SQL Editor, in order:
`0001_schema.sql`, `0002_rls.sql`, `0003_api_readonly.sql`,
`0004_add_bachata.sql`.
