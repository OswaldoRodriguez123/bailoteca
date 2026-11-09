# Monorepo parser/api/web/shared — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reestructurar `bailoteca` en un monorepo con `parser/`, `api/`, `web/` y `shared/`, conservando el comportamiento del parser y dejando API/web documentados pero sin implementar.

**Architecture:** Monorepo en el mismo repo con `git mv`. `shared/` es un paquete Python con la conexión y las consultas de lectura; el parser lo consume y reexporta para no romper imports. `api/` y `web/` son documentación + `.env.example` por ahora.

**Tech Stack:** Python 3.12, setuptools, psycopg 3, pydantic 2, pytest, GitHub Actions, Supabase Postgres.

**Spec:** `docs/superpowers/specs/2026-11-09-monorepo-design.md`

## Global Constraints

- Python `>=3.12`.
- No cambiar comportamiento del parser, del filtro de ruido ni de la publicación.
- No versionar `.env` ni secretos.
- Instalación local: `pip install -e shared -e "parser[dev]"`.
- `supabase/migrations/` queda en la raíz.
- `api/` y `web/` no llevan implementación todavía.
- El cron mensual y el `workflow_dispatch` deben seguir funcionando.
- Usar `git mv` para archivos versionados; `mv` para directorios ignorados (`reports/`).

## Review Focus

- **Imports rotos al mover paquetes:** cualquier `from bailoteca...` debe seguir resolviendo desde `parser/src`.
- **`shared` sin instalar:** el parser debe fallar claro si falta `bailoteca_shared`; el README debe indicar el orden de instalación.
- **Rutas del workflow:** cache en `parser/data/cache/serpapi`, artefacto en `parser/reports/`, ejecución con `working-directory: parser`.
- **`.env` filtrado:** `parser/.env` debe quedar ignorado y no aparecer en `git status`.
- **Tests del parser:** la suite debe pasar igual que antes (91 tests).

---

### Task 1: Crear `shared/` y mover la capa de lectura

**Files:**
- Create: `shared/pyproject.toml`
- Create: `shared/src/bailoteca_shared/__init__.py`
- Create: `shared/src/bailoteca_shared/db.py`
- Create: `shared/src/bailoteca_shared/schema.py`
- Create: `shared/tests/test_schema.py`
- Modify: `src/bailoteca/db.py` (quitar `connect`, `list_published`, `academy_id_by_slug`; reexportarlos)

**Interfaces:**
- Produces: `bailoteca_shared.db.connect(database_url: str) -> psycopg.Connection`
- Produces: `bailoteca_shared.db.list_published(conn) -> list[dict]`
- Produces: `bailoteca_shared.db.academy_id_by_slug(conn, slug: str) -> str | None`
- Produces: `bailoteca_shared.schema.Academy`, `AcademyLocation`, `AcademyLink`, `AcademyStyle` (Pydantic 2).

- [ ] **Step 1: Crear el paquete y su `pyproject.toml`**

`shared/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "bailoteca-shared"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "psycopg[binary]>=3.2",
  "pydantic>=2.8",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Instalar `shared` en editable**

Run: `.venv/bin/pip install -e shared`
Expected: instala `bailoteca-shared`.

- [ ] **Step 3: Escribir el test de esquema (RED)**

`shared/tests/test_schema.py`:

```python
from bailoteca_shared.schema import Academy


def test_academy_accepts_list_published_shape():
    academy = Academy.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "slug": "danson-academy",
            "name": "Dansón Academy",
            "description": "Salsa cubana.",
            "status": "unknown",
            "source_urls": [],
            "created_at": "2026-11-09T00:00:00Z",
            "updated_at": "2026-11-09T00:00:00Z",
            "verified_at": "2026-11-09T00:00:00Z",
            "locations": [
                {"label": "Santiago", "address": None, "comuna": "Santiago",
                 "lat": None, "lng": None, "source_url": None}
            ],
            "links": [{"kind": "web", "url": "https://danson.cl"}],
            "styles": [{"slug": "salsa-cubana", "name": "Salsa cubana",
                        "confidence": 0.9, "evidence": "casino"}],
        }
    )
    assert academy.slug == "danson-academy"
    assert academy.locations[0].comuna == "Santiago"
```

- [ ] **Step 4: Correr el test y verlo fallar**

Run: `.venv/bin/python -m pytest shared/tests/test_schema.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'bailoteca_shared.schema'`.

- [ ] **Step 5: Implementar `schema.py`**

Modelos Pydantic 2 con `model_config = ConfigDict(extra="ignore")`:

```python
class AcademyLocation(BaseModel):
    label: str | None = None
    address: str | None = None
    comuna: str | None = None
    lat: float | None = None
    lng: float | None = None
    source_url: str | None = None


class AcademyLink(BaseModel):
    kind: str
    url: str


class AcademyStyle(BaseModel):
    slug: str
    name: str | None = None
    confidence: float | None = None
    evidence: str | None = None


class Academy(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    status: str
    source_urls: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    verified_at: datetime | None = None
    locations: list[AcademyLocation] = []
    links: list[AcademyLink] = []
    styles: list[AcademyStyle] = []
```

- [ ] **Step 6: Verificar el test en verde**

Run: `.venv/bin/python -m pytest shared/tests/test_schema.py -q`
Expected: PASS.

- [ ] **Step 7: Mover la capa de lectura a `shared/db.py`**

Copiar exactamente `connect`, `list_published` y `academy_id_by_slug` desde `src/bailoteca/db.py`. Ajustar imports (`psycopg`, `dict_row`).

- [ ] **Step 8: Reexportar desde el parser**

En `src/bailoteca/db.py`, eliminar las tres funciones movidas y agregar:

```python
from bailoteca_shared.db import (  # noqa: F401
    academy_id_by_slug,
    connect,
    list_published,
)
```

Los imports internos del parser (`from bailoteca.db import list_published`) no cambian.

- [ ] **Step 9: Correr la suite del parser**

Run: `TEST_DATABASE_URL=postgresql://postgres:zumba@localhost:5432/bailoteca_dev .venv/bin/python -m pytest -q`
Expected: 91 passed.

- [ ] **Step 10: Commit**

```bash
git add shared src/bailoteca/db.py
git commit -m "refactor: extract shared read layer"
```

---

### Task 2: Mover el parser a `parser/` y recrear el entorno

**Files:**
- Move: `src/` → `parser/src/`
- Move: `tests/` → `parser/tests/`
- Move: `data/` → `parser/data/`
- Move: `reports/` → `parser/reports/` (ignorado, `mv`)
- Move: `scripts/` → `parser/scripts/`
- Move: `docs/osm-spike.md` → `parser/docs/osm-spike.md`
- Move: `pyproject.toml` → `parser/pyproject.toml`
- Move: `.env.example` → `parser/.env.example`
- Move: `.env` → `parser/.env` (ignorado, `mv`)

**Interfaces:**
- Consumes: `bailoteca_shared` instalado en Task 1.
- Produces: paquete `bailoteca` ejecutable desde `parser/` con `python -m bailoteca`.

- [ ] **Step 1: Mover archivos versionados**

```bash
mkdir -p parser/docs
git mv src parser/src
git mv tests parser/tests
git mv data parser/data
git mv scripts parser/scripts
git mv docs/osm-spike.md parser/docs/osm-spike.md
git mv pyproject.toml parser/pyproject.toml
git mv .env.example parser/.env.example
```

- [ ] **Step 2: Mover archivos ignorados**

```bash
mv reports parser/reports
mv .env parser/.env
```

- [ ] **Step 3: Ajustar `parser/pyproject.toml`**

- `name = "bailoteca-parser"`.
- Mantener dependencias, `[project.scripts]` y `testpaths = ["tests"]`.
- No declarar `bailoteca-shared` como dependencia de PyPI; se instala aparte.

- [ ] **Step 4: Recrear el `.venv` raíz**

```bash
rm -rf .venv
python3.12 -m venv .venv
.venv/bin/pip install -e shared -e "parser[dev]"
```

- [ ] **Step 5: Correr la suite desde la raíz**

Run: `TEST_DATABASE_URL=postgresql://postgres:zumba@localhost:5432/bailoteca_dev .venv/bin/python -m pytest parser/tests shared/tests -q`
Expected: 92 passed (91 + schema).

- [ ] **Step 6: Verificar el CLI desde `parser/`**

Run: `cd parser && ../.venv/bin/python -m bailoteca --help`
Expected: muestra los comandos (`run`, `review`, `approve`, `export`, etc.).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: move parser into parser/"
```

---

### Task 3: Crear `api/` y `web/` (solo estructura)

**Files:**
- Create: `api/README.md`
- Create: `api/.env.example`
- Create: `web/README.md`
- Create: `web/.env.example`

- [ ] **Step 1: `api/README.md`**

Debe describir: FastAPI, endpoints previstos (`GET /health`, `GET /academies`, `GET /academies/{slug}`), uso de `DATABASE_URL_READONLY`, dependencia de `bailoteca_shared.schema`, y cómo correr más adelante (`pip install -e shared -e api`, `uvicorn`).

- [ ] **Step 2: `api/.env.example`**

```bash
DATABASE_URL_READONLY=
CORS_ORIGINS=http://localhost:4200
```

- [ ] **Step 3: `web/README.md`**

Debe describir: Angular, consumo de `API_BASE_URL`, estructura prevista, y que en Vercel el Root Directory será `web/`.

- [ ] **Step 4: `web/.env.example`**

```bash
API_BASE_URL=http://localhost:8000
```

- [ ] **Step 5: Commit**

```bash
git add api web
git commit -m "docs: scaffold api and web placeholders"
```

---

### Task 4: READMEs raíz/parser y `.gitignore`

**Files:**
- Move: `README.md` → `parser/README.md`
- Create: `README.md` (nuevo, raíz)
- Modify: `.gitignore`
- Modify: `parser/.env.example` (si menciona rutas viejas)

- [ ] **Step 1: Mover el README actual**

```bash
git mv README.md parser/README.md
```

Ajustar en `parser/README.md`: instalación (`pip install -e shared -e "parser[dev]"`), comandos ejecutados desde `parser/`, rutas `data/` y `reports/`.

- [ ] **Step 2: Crear el README raíz**

Debe incluir: qué es Bailoteca, diagrama de carpetas, tabla de componentes, quickstart del parser, estado de API/web, despliegue (Vercel Root Directory `api/` y `web/`, Actions para `parser/`), política de secretos y enlace a `supabase/migrations/` y a los specs.

- [ ] **Step 3: Actualizar `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
parser/data/cache/*
!parser/data/cache/.gitkeep
parser/reports/
*.egg-info/
```

- [ ] **Step 4: Commit**

```bash
git add README.md parser/README.md .gitignore parser/.env.example
git commit -m "docs: rewrite root README for monorepo"
```

---

### Task 5: Mover y ajustar el workflow

**Files:**
- Move: `.github/workflows/weekly.yml` → `.github/workflows/parser.yml`
- Modify: `.github/workflows/parser.yml`

- [ ] **Step 1: Mover el workflow**

```bash
git mv .github/workflows/weekly.yml .github/workflows/parser.yml
```

- [ ] **Step 2: Aplicar `paths` y nuevas rutas**

- `name: Actualizar Bailoteca (parser)`.
- Mantener `schedule` y `workflow_dispatch`.
- Agregar `push` y `pull_request` con `paths: ["parser/**", "shared/**", ".github/workflows/parser.yml"]`.
- Instalar con `pip install -e shared -e "parser[dev]"`.
- Tests: `pytest parser/tests shared/tests -q`.
- Cache: `path: parser/data/cache/serpapi`.
- Ejecución: `working-directory: parser` con `python -m bailoteca run` (y `--dry-run` si `inputs.dry_run`).
- Artefacto: `path: parser/reports/`.

- [ ] **Step 3: Validar el YAML**

Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/parser.yml'))"`
Expected: sin error. Si falta PyYAML, revisar el archivo a mano y anotarlo.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/parser.yml
git commit -m "ci: scope parser workflow by path"
```

---

### Task 6: Verificación final

- [ ] **Step 1: Suite completa**

Run: `TEST_DATABASE_URL=postgresql://postgres:zumba@localhost:5432/bailoteca_dev .venv/bin/python -m pytest parser/tests shared/tests -q`
Expected: todos en verde.

- [ ] **Step 2: Dry-run del parser desde `parser/`**

Run: `cd parser && BAILOTECA_SOURCES=seed ../.venv/bin/python -m bailoteca run --dry-run`
Expected: termina sin error y escribe en `parser/reports/`.

- [ ] **Step 3: Export contra la base real**

Run (cargando `parser/.env` sin imprimirlo): `cd parser && ../.venv/bin/python -m bailoteca export --csv`
Expected: 16 academias.

- [ ] **Step 4: Revisar el diff y el estado**

Run: `git status --short && git diff --stat`
Expected: sin `.env`, sin `data/cache`, sin artefactos generados.

- [ ] **Step 5: Commit de correcciones si hubo**

```bash
git add -A
git commit -m "chore: finish monorepo restructure"
```
