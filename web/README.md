# Bailoteca web

Angular 22 SPA with Tailwind CSS 4 that consumes the Bailoteca public read-only
API. It uses no SSR or SSG, does not include NgRx and has no database access:
everything goes through the public endpoints.

## Stack

- Angular 22 with standalone components, signals and lazy routes.
- Tailwind CSS 4 (CSS-first configuration, no `tailwind.config.js`).
- Vitest 5 with `jsdom` for unit tests.
- TypeScript 6.

## Structure

```text
web/
├── scripts/write-env.mjs             # generates environment.production.ts before the build
├── src/
│   ├── environments/                 # development and production
│   └── app/
│       ├── core/                     # API_BASE_URL token, models, HTTP client, error messages
│       ├── shared/components/        # EmptyState, ErrorState, LoadingGrid
│       └── features/academies/
│           ├── academy-list/         # list with filters and pagination
│           ├── academy-detail/       # detail by slug
│           ├── academy-display.ts    # labels, maps and comunas
│           ├── academy-query.ts      # URL normalization
│           └── components/           # AcademyCard, FilterBar, Pagination, StyleBadges
└── vercel.json
```

## Requirements

- Node.js 24
- npm 11
- The API running (on `http://localhost:8000` by default)

## Development

```bash
cd web
npm install
npm start
```

The app runs at `http://localhost:4200` and reads `API_BASE_URL` from
`src/environments/environment.ts` (`http://localhost:8000` by default).

## Tests

```bash
cd web
npm test -- --watch=false
```

The tests use `HttpTestingController` and fixtures; they do not need the real
API.

## Production build

```bash
cd web
API_BASE_URL=https://api.example.com npm run build
```

`API_BASE_URL` is required: the `prebuild` script (`scripts/write-env.mjs`)
fails when it is missing and writes `src/environments/environment.production.ts`
before compiling. The output goes to `dist/bailoteca-web/browser/`.

## Variables

| Variable       | Where                          | Use                                   |
| -------------- | ------------------------------ | ------------------------------------- |
| `API_BASE_URL` | build environment / `.env`     | Base URL of the public API            |

There are no secrets in the browser. `web/.env.example` only documents
`API_BASE_URL`.

## Endpoints consumed

| Method | Endpoint             | Use                                    |
| ------ | -------------------- | -------------------------------------- |
| `GET`  | `/academies`         | List with `comuna`, `style`, `q`, `page`, `page_size` |
| `GET`  | `/academies/{slug}`  | Academy detail                         |
| `GET`  | `/styles`            | Style filter options                   |
| `GET`  | `/comunas`           | Comuna filter options                  |

The client lives in `src/app/core/services/academies-api.ts` and only performs
reads.

## Routes

| Route              | Page                                       |
| ------------------ | ------------------------------------------ |
| `/`                | List with filters, search and pagination   |
| `/academias/:slug` | Academy detail                             |

Both are loaded with `loadComponent` (lazy). An unknown route redirects to `/`.

## Decisions

- **The URL is the list state**: `comuna`, `style`, `q` and `page` live in query
  params. Search is debounced 300 ms and rewrites the URL with `replaceUrl`, so
  the back button does not store every keystroke.
- **No `status` filter in the client**: every academy the API returns is shown;
  closed ones carry the "Cerrada" badge and unverified ones "Sin verificar".
- **Internal data hidden**: `confidence`, `evidence`, `source_url` and
  `source_urls` are not rendered. Only public data is shown.
- **Invalid input is normalized**: styles with an invalid format, one-character
  searches and out-of-range pages are corrected in the URL.
- **Card links keep the filters** so you return to the same list.

## Deploying to Vercel

1. Create a project with **Root Directory** `web/`.
2. Build command: `npm run build`.
3. Output directory: `dist/bailoteca-web/browser`.
4. Set `API_BASE_URL` to the public API URL in the project environment
   variables.
5. `vercel.json` rewrites every route to `index.html` so the Angular router
   works on reload.

The API must allow the site origin in `CORS_ORIGINS`
(`https://<project>.vercel.app`). The `.github/workflows/web.yml` CI runs tests
and the build with a placeholder `API_BASE_URL` when `web/**` changes.

Production site: <https://bailoteca.vercel.app>, with
`API_BASE_URL=https://bailoteca-api.vercel.app`.
