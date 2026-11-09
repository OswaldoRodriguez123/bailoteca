# Bailoteca

Directorio de academias de baile en Santiago de Chile, empezando por salsa.
Monorepo con un pipeline de datos, una API de solo lectura y una web, sobre un
esquema Postgres compartido.

- **Costo $0**: Supabase free, GitHub Actions y fuentes gratuitas.
- **Publicado = aprobado por una persona**: el pipeline propone; la CLI publica.
- **Sin scraping de Instagram**: se guarda el handle público como enlace.

## Componentes

| Carpeta   | Qué es                                                        | Estado        |
| --------- | ------------------------------------------------------------- | ------------- |
| `parser/` | Pipeline: descubrir → filtrar → enriquecer → clasificar → proponer | Funcionando |
| `shared/` | Paquete `bailoteca-shared`: conexión, lecturas y DTOs Pydantic | Funcionando |
| `api/`    | FastAPI de solo lectura                                        | Documentado   |
| `web/`    | Angular                                                        | Documentado   |
| `supabase/migrations/` | Esquema y RLS compartidos                         | Funcionando   |

```text
bailoteca/
├── parser/                  # pipeline + CLI
│   ├── src/bailoteca/
│   ├── tests/
│   ├── data/                # seed.csv + caché (ignorada)
│   └── reports/             # reportes por corrida (ignorados)
├── shared/                  # bailoteca-shared
│   ├── src/bailoteca_shared/
│   └── tests/
├── api/                     # README + .env.example
├── web/                     # README + .env.example
├── supabase/migrations/     # 0001_schema.sql, 0002_rls.sql
├── docs/superpowers/        # specs y planes
└── .github/workflows/parser.yml
```

## Quickstart del parser

Requisitos: Python 3.12+, un Postgres 14+ (Supabase free sirve) y, opcional, una
API key de Gemini.

```bash
# 1. Entorno e instalación (desde la raíz)
python -m venv .venv
.venv/bin/pip install -e shared -e "parser[dev]"

# 2. Configuración
cp parser/.env.example parser/.env
# editar parser/.env con DATABASE_URL y las claves opcionales

# 3. Migraciones (SQL Editor de Supabase, en orden)
#    supabase/migrations/0001_schema.sql
#    supabase/migrations/0002_rls.sql

# 4. Correr el pipeline
cd parser
../.venv/bin/python -m bailoteca run --dry-run   # sin escribir en la BD
../.venv/bin/python -m bailoteca run             # escribe propuestas
../.venv/bin/python -m bailoteca review          # ver pendientes
../.venv/bin/python -m bailoteca approve <id>    # publicar
```

Detalles del pipeline, filtro de ruido, fuentes y cuota de SerpApi en
[`parser/README.md`](parser/README.md).

## Tests

```bash
# desde la raíz
.venv/bin/python -m pytest parser/tests shared/tests -q

# integración contra un Postgres de prueba
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/bailoteca_test \
  .venv/bin/python -m pytest parser/tests shared/tests -q
```

## API y web

Ambas carpetas contienen solo el contrato y las decisiones de despliegue:

- [`api/README.md`](api/README.md): FastAPI, endpoints previstos y usuario
  read-only.
- [`web/README.md`](web/README.md): Angular y consumo de `API_BASE_URL`.

## Despliegue

- **Parser**: GitHub Actions, `.github/workflows/parser.yml`, el **1° de cada
  mes a las 03:00 UTC**. Solo corre por cron o manualmente
  (`workflow_dispatch`); un push no lo dispara.
- **API**: Vercel con Root Directory `api/`.
- **Web**: Vercel con Root Directory `web/`.
- **Base de datos**: Supabase; las migraciones se aplican a mano desde el SQL
  Editor.

## Secretos

Ningún `.env` se versiona. Cada componente tiene su `.env.example`:

| Componente | Variables |
| ---------- | --------- |
| Parser     | `DATABASE_URL` (escritura), `GEMINI_API_KEY`, `SERPAPI_KEY`, `CLOUDFLARE_*` |
| API        | `DATABASE_URL_READONLY`, `CORS_ORIGINS` |
| Web        | `API_BASE_URL` |

En GitHub Actions, los secretos del parser se configuran en
`Settings → Secrets and variables → Actions`. La API usará un usuario de
Supabase con permiso solo de lectura, que se creará cuando se implemente.

## Documentación

- Diseño del monorepo: `docs/superpowers/specs/2026-11-09-monorepo-design.md`
- Plan de migración: `docs/superpowers/plans/2026-11-09-monorepo-restructure.md`
- Spike de OSM: `parser/docs/osm-spike.md`
