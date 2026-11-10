# Bailoteca Parser

**Bailoteca Parser** is the pipeline behind a dance school directory in Santiago.
It discovers candidates from free sources, classifies them by style with
evidence, and leaves proposals for a person to approve before publishing.

This package lives in `parser/` inside the monorepo. Connection and read queries
come from `shared/` (`bailoteca-shared`); the parser keeps the writes and the
CLI.

- **Published** = the row exists in the `academies` table. Only the CLI writes
  there, after approval.
- **Styles** are multilabel over a taxonomy stored in the `styles` table.
  Adding a style is inserting rows, not migrating columns.
- **$0 cost**: free Postgres on Supabase, GitHub Actions and free sources.
  Gemini is optional; without a key the system classifies with rules only.

## Requirements

- Python 3.12 or newer.
- A Supabase project (free) or any Postgres 14+.
- Optional: a Gemini API key to improve classification.

## Setup

1. Create the Supabase project and copy the connection string
   (`Project Settings → Database → Connection string`).
2. Apply every file in `supabase/migrations/` in order from the SQL Editor.

   `0002` enables RLS and leaves the anonymous key read-only on the published
   tables. The migrations live at the repo root because the schema is shared
   with the API.

3. Copy `.env.example` to `.env` and fill in the values:

   ```bash
   cp .env.example .env
   ```

   `DATABASE_URL` is a secret: it is not versioned and never pasted into chat.
   The Supabase anonymous key is for reading from the frontend, never for
   writing.

4. Install the packages from the repo root:

   ```bash
   python -m venv .venv
   .venv/bin/pip install -e shared -e "parser[dev]"
   ```

   `bailoteca-shared` must be installed before or together with the parser;
   without it the read imports fail.

5. Fill `data/seed.csv` with the academies you already know:

   ```csv
   name,url,instagram,comuna
   Academia Ejemplo,https://ejemplo.cl,@ejemplo,Providencia
   ```

   `url` and `instagram` are optional; an academy with only Instagram is still
   published, as unverified.

## Usage

All commands run from `parser/` with the virtualenv active
(`source ../.venv/bin/activate`):

```bash
# Discover and generate proposals without touching the database
bailoteca run --dry-run

# Same, writing proposals to Postgres
bailoteca run

# List pending proposals in Markdown
bailoteca review

# Approve a proposal (sets verified_at)
bailoteca approve <proposal-id>

# Approve an incomplete record without marking it verified
bailoteca approve <proposal-id> --unverified

# Fix and approve (opens $EDITOR with the JSON payload)
bailoteca edit <proposal-id>

# Discard a proposal
bailoteca reject <proposal-id>

# Add an academy by hand: @handle, URL or name
bailoteca add "@academia_ejemplo"

# Re-read a published academy and propose only the differences
bailoteca refresh academia-ejemplo

# Export what is published
bailoteca export
bailoteca export --csv
```

Each run writes `reports/<date>/` with `candidates.json`, `proposals.json`,
`review.md` and `summary.md`.

## Tests

From the repo root:

```bash
.venv/bin/python -m pytest parser/tests shared/tests -q
```

Integration tests are skipped when `TEST_DATABASE_URL` is missing. To run them
against a test Postgres:

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

## Monthly update

`.github/workflows/parser.yml` runs on the **1st of each month at 03:00 UTC**:

1. installs dependencies (`shared` + `parser`),
2. runs the test suite,
3. runs `bailoteca run` with the repository secrets,
4. uploads `parser/reports/` as an artifact.

The workflow only runs on the monthly cron or manually with
`workflow_dispatch`; a push does not run the pipeline.

Configure in GitHub `Settings → Secrets and variables → Actions`:
`DATABASE_URL`, `GEMINI_API_KEY` and `SERPAPI_KEY` (the latter is
**recommended** for web discovery). Optionally `BRAVE_API_KEY`,
`CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` for noise triage.

### Noise filter

Every run goes through two stages before creating proposals:

```text
discover → deterministic rules → enrich → Clef → proposals
```

1. **Rules** (`bailoteca/sources/filters.py`): drop directories
   (`superprof.cl`, `salirsantiago.com`, `2x3.cl`…), social posts/videos/events
   and Instagram `/popular/` pages. They keep profiles and homepages of
   Facebook groups.
2. **Clef** (`@cf/cloudflare/clef-flash`): judges, with ~600 characters of the
   page's real text, whether it is a dance academy in the Metropolitan Region
   that teaches the styles in the taxonomy. Threshold
   `min(academia, salsa, santiago) >= 0.5`.

Discards are **not stored** in the database: they are discovered and judged
again next month. If the Cloudflare credentials are missing or Clef fails, the
candidate passes (**fail-open**), so real academies are not lost. The counters
`filtrados_reglas`, `filtrados_clef` and `clef_errors` appear in the log and in
`summary.md`.

Sources (`BAILOTECA_SOURCES`):

- `seed,serpapi` (recommended): curated CSV + Google Search through SerpApi.
- `seed,brave`: curated CSV + web search through the Brave Search API (free
  plan, requires `BRAVE_API_KEY`; it does not use scraped endpoints: token API,
  no anti-bot blocking).
- `seed,search`: CSV + DuckDuckGo HTML. **DDG usually blocks** with an
  `anomaly.js` page (status 202) on datacenter IPs; use it only as a manual
  fallback.
- `seed,search,osm`: also OSM, disabled by default.

> Quota note: SerpApi free = ~250 req/month. The full monthly run
> (10 comunas × 4 variants = 40 queries) stays well under the limit.
>
> SerpApi responses are cached in `data/cache/serpapi/` with a **24 h TTL**, per
> query and without the `api_key` in the key. Repeating a run on the same day
> spends no searches; the monthly cron always refreshes. If the cache file is
> corrupt or cannot be written, it is ignored and the API is queried again. In
> GitHub Actions `data/cache/serpapi` is restored with `actions/cache`, so
> re-running the workflow on the same day spends no searches either; the monthly
> cron always finds the cache expired.

The monthly run **does not re-download** published academies; it only checks
links. To re-read a specific record, use `bailoteca refresh <slug>`.

### OSM

`OverpassSource` is implemented but disabled by default. The 2026-11-09 spike
could not measure its coverage because the network blocked both endpoints; see
`docs/osm-spike.md`. It can be enabled with `BAILOTECA_SOURCES=seed,search,osm`
once there is network and the cutoff criterion is validated.

## Security

- RLS is active on all eight tables.
- The anonymous key only runs `select` on `styles`, `academies`,
  `academy_locations`, `academy_links` and `academy_styles`.
- There are no write policies for `anon`.
- `candidates`, `proposals` and `field_rejections` are only read and written
  with the service key (the CLI).
- Instagram is not scraped: the public handle is stored as a link.
- Raw HTML stays in `data/cache/` (git-ignored) and as a workflow artifact,
  never in the database.

## Structure

```text
parser/
  src/bailoteca/
    cli.py        # bailoteca commands
    config.py     # environment reading
    db.py         # SQL writes; re-exports the reads from shared
    discover.py   # deduplication across sources
    enrich.py     # safe download, JSON-LD, socials and cache
    classify.py   # rules + LLM merge
    propose.py    # payloads, dedupe and rejections
    publish.py    # validation, approval and publishing
    run.py        # full run, dry-run and refresh
    links.py      # dead links
    report.py     # run report
  tests/
  data/seed.csv
  reports/
shared/           # connection, reads and DTOs shared with the API
supabase/migrations/
```

## v1 limitations

- No schedules or prices.
- The API and web app live in `api/` and `web/`; this package only writes to the
  database.
- Only Santiago comunas in the search queries.
- `verified_at` is only set by a person; an automated run never touches it.
