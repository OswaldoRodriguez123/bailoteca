# Bailoteca API

API de solo lectura para el directorio de academias de Bailoteca. Todavía no
tiene implementación: esta carpeta define el contrato y las decisiones para
cuando se construya.

## Stack previsto

- **FastAPI** + **Uvicorn**.
- **`bailoteca-shared`** para la conexión y los modelos de respuesta
  (`Academy`, `AcademyLocation`, `AcademyLink`, `AcademyStyle`).
- Postgres de Supabase con un usuario **read-only**.

## Endpoints previstos

| Método | Ruta                  | Descripción                                  |
| ------ | --------------------- | -------------------------------------------- |
| `GET`  | `/health`             | Estado del servicio y de la conexión a la BD |
| `GET`  | `/academies`          | Lista de academias publicadas                |
| `GET`  | `/academies/{slug}`   | Detalle de una academia por slug             |

La respuesta de `/academies` y `/academies/{slug}` se serializa con
`bailoteca_shared.schema.Academy`, el mismo contrato que usa el parser. No se
inventan modelos nuevos en la API.

## Variables de entorno

Copiar `.env.example` a `.env`:

```bash
cp .env.example .env
```

- `DATABASE_URL_READONLY`: cadena de conexión con un usuario que solo puede
  `select` sobre las tablas publicadas. **No** usar la llave de escritura del
  parser.
- `CORS_ORIGINS`: orígenes permitidos, separados por coma. En local,
  `http://localhost:4200`.

El usuario read-only se crea en Supabase cuando la API se implemente; por ahora
solo queda documentado. Ningún `.env` se versiona.

## Cómo correrla (cuando exista el código)

```bash
# desde la raíz del repo
.venv/bin/pip install -e shared -e "api[dev]"
.venv/bin/uvicorn bailoteca_api.main:app --reload
```

## Despliegue

- Vercel con **Root Directory** en `api/`.
- Variables de entorno configuradas en Vercel, nunca en el repo.
- Sin workflow de CI hasta que exista código; cuando exista, se filtra por
  `paths: api/**, shared/**`.
