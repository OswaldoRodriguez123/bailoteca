# bailoteca-shared

Paquete Python con lo que el parser y la API comparten:

- `bailoteca_shared.db`: `connect`, `list_published`, `academy_id_by_slug`
  (solo lectura; no hace commit).
- `bailoteca_shared.schema`: DTOs Pydantic 2 (`Academy`, `AcademyLocation`,
  `AcademyLink`, `AcademyStyle`) que definen el contrato de respuesta.

## Instalación

Desde la raíz del repo:

```bash
.venv/bin/pip install -e shared
```

El parser lo instala junto con sus dependencias:

```bash
.venv/bin/pip install -e shared -e "parser[dev]"
```

## Tests

```bash
.venv/bin/python -m pytest shared/tests -q
```
