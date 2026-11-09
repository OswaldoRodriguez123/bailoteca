# Diseño: monorepo parser + api + web + shared

**Fecha:** 2026-11-09
**Estado:** propuesto (pendiente de aprobación)

## Intención

Convertir `bailoteca` en un monorepo con cuatro carpetas:

```
bailoteca/
├── parser/   # pipeline actual: descubrir → enriquecer → clasificar → publicar
├── api/      # FastAPI (estructura y documentación ahora; implementación después)
├── web/      # Angular (estructura y documentación ahora; implementación después)
└── shared/   # modelos y acceso a BD comunes a parser y api
```

El objetivo es que el parser y la futura API compartan el mismo esquema y la
misma capa de lectura, sin duplicar código, y que el repo se lea como un
sistema completo en el portafolio.

## Objetivos

- Mover el código actual del parser a `parser/` conservando historial y
  comportamiento.
- Crear `shared/` como paquete Python real, usado por el parser hoy y por la
  API después.
- Separar dependencias, secretos y CI por componente.
- Dejar `api/` y `web/` con README, `.env.example` y decisiones de despliegue,
  sin implementar endpoints ni UI.
- README raíz que explique la arquitectura y cómo correr cada parte.
- Los tests del parser y de `shared` siguen pasando.

## No objetivos

- Implementar FastAPI o Angular en esta etapa.
- Desplegar en Vercel ahora.
- Crear el usuario read-only de Supabase ahora (solo documentar).
- Cambiar el comportamiento del pipeline, del filtro de ruido o de la
  publicación.

## Anti-objetivos

- Duplicar `db.py` o los modelos entre parser y API.
- Un único `requirements.txt` para todo el monorepo.
- Un workflow que corra todos los tests en cada cambio.
- Romper el cron mensual del parser.

## Enfoques considerados

1. **Repo nuevo y dejar `bailoteca` como parser.** Descartado: parte el
   historial y obliga a clonar/versionar dos repos.
2. **Monorepo en el mismo repo con `git mv`.** Elegido: conserva historial,
   un solo clon, despliegues independientes por Root Directory.
3. **Monorepo sin `shared/`.** Descartado: parser y API duplicarían conexión,
   consultas y modelos; el esquema se desincroniza.

## Estructura objetivo

```
bailoteca/
├── README.md                     # arquitectura, quickstart, despliegue
├── .gitignore
├── .github/workflows/parser.yml  # cron mensual + tests con paths
├── docs/superpowers/specs/       # este documento
├── supabase/migrations/          # esquema compartido
├── shared/
│   ├── pyproject.toml            # bailoteca-shared
│   ├── README.md
│   ├── src/bailoteca_shared/
│   │   ├── __init__.py
│   │   ├── db.py                 # connect, list_published, academy_id_by_slug
│   │   └── schema.py             # DTOs Pydantic para la API
│   └── tests/
├── parser/
│   ├── pyproject.toml            # bailoteca-parser (deps pesadas + CLI)
│   ├── README.md
│   ├── .env.example
│   ├── src/bailoteca/            # código actual
│   ├── tests/
│   ├── data/                     # seed.csv + cache
│   ├── reports/
│   ├── scripts/
│   └── docs/osm-spike.md
├── api/
│   ├── README.md
│   └── .env.example
└── web/
    ├── README.md
    └── .env.example
```

## Decisiones

### `shared/`

- `bailoteca_shared/db.py`: `connect`, `list_published`, `academy_id_by_slug`.
  Solo lectura; no importa nada del parser.
- `bailoteca_shared/schema.py`: modelos Pydantic de respuesta (`Academy`,
  `AcademyLocation`, `AcademyLink`, `AcademyStyle`) para que la API no invente
  su propio contrato.
- `parser/src/bailoteca/db.py` se queda con las escrituras
  (`upsert_candidate`, `insert_proposal`, `record_field_rejections`,
  `pending_proposals`, `rejected_values`) y **reexporta** las funciones de
  lectura de `shared`. Así los imports internos del parser no cambian.
- Instalación local: `pip install -e shared -e "parser[dev]"`. Queda documentado
  en el README raíz y en `parser/README.md`.

### Parser

- Conserva el paquete `bailoteca`, su CLI, tests y dependencias.
- `data/`, `reports/`, `scripts/` y `docs/osm-spike.md` se mueven dentro de
  `parser/`.
- `.env` actual se mueve a `parser/.env` (sigue en `.gitignore`).
- `supabase/migrations/` queda en la raíz porque el esquema es compartido.

### API y web (solo estructura)

- `api/README.md`: FastAPI, endpoints previstos, usuario read-only, variables.
- `web/README.md`: Angular, consumo de la API, Root Directory en Vercel.
- `.env.example` por componente. La API usará `DATABASE_URL_READONLY`; el
  parser `DATABASE_URL` de escritura; la web solo `API_BASE_URL`.
- No se crean workflows de API/web hasta que exista código.

### CI

- `.github/workflows/weekly.yml` → `.github/workflows/parser.yml`.
- `paths`: `parser/**`, `shared/**`, `.github/workflows/parser.yml`.
- Mantiene cron mensual, `workflow_dispatch`, cache de SerpApi en
  `parser/data/cache/serpapi` y artefacto en `parser/reports/`.
- La instalación del job pasa a `pip install -e shared -e "parser[dev]"`.

### Secretos

- Parser: `DATABASE_URL` con permiso de escritura, `SERPAPI_KEY`,
  `GEMINI_API_KEY`, `CLOUDFLARE_*`.
- API: `DATABASE_URL_READONLY` (se crea después en Supabase).
- Web: solo `API_BASE_URL`.
- Ningún `.env` se versiona.

## Migración

1. Crear `shared/` y mover `connect`, `list_published`, `academy_id_by_slug` y
   los DTOs. Ajustar el parser con reexports.
2. `git mv` de `src/`, `tests/`, `data/`, `reports/`, `scripts/` y
   `docs/osm-spike.md` a `parser/`.
3. Crear `shared/pyproject.toml` y `parser/pyproject.toml`.
4. Recrear `.venv` e instalar ambos paquetes en editable.
5. Mover el workflow y aplicar `paths`.
6. Actualizar `.gitignore`, `.env.example` y READMEs.
7. Verificar con tests, `run --dry-run` y `export`.

## Verificación

- `pytest` del parser y de `shared` en verde.
- `cd parser && python -m bailoteca run --dry-run` funciona.
- `cd parser && python -m bailoteca export --csv` funciona.
- El workflow no se dispara por cambios en `api/` o `web/`.
- `git status` sin secretos ni artefactos generados.
- El cron y las rutas de cache/reportes quedan coherentes con la nueva
  estructura.

## Riesgos

- **Imports rotos al mover:** se cubren con reexports y la suite completa.
- **`.venv` existente deja de servir:** se recrea e instala editable.
- **Cron con rutas viejas:** se revisa el YAML y se prueba un dry-run local.
- **Pérdida de historial:** se usa `git mv`, no copiar/borrar.
