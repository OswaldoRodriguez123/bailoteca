# Spike de OpenStreetMap — 2026-11-09

## Objetivo

Medir si OSM aporta academias de baile útiles para Gran Santiago antes de
activarlo como fuente por defecto.

Criterio de corte del diseño: **se conserva** si aporta al menos 10 academias
válidas nuevas (o ~30% del tamaño de la semilla); si no, **se descarta** y el
adaptador queda detrás de `BAILOTECA_SOURCES`.

## Bbox consultado

`(-33.65, -70.85, -33.30, -70.50)` — Gran Santiago.

Tags: `amenity=dancing_school`, `leisure=dance`, `sport=dancing` en nodos y
ways, con `out center tags`.

## Endpoints probados

| Endpoint | Resultado |
| --- | --- |
| `https://overpass-api.de/api/interpreter` | timeout a los 8 s (`http=000`) |
| `https://overpass.kumi.systems/api/interpreter` | timeout a los 8 s (`http=000`) |

La red de este entorno no permite alcanzar Overpass. Se intentó también con el
wrapper completo (`scripts/osm_spike.py`) con timeout de 60 s por endpoint; la
ejecución superó los 3 minutos sin respuesta.

## Conteos del fixture

Para verificar el código de resumen se usó el fixture
`tests/fixtures/overpass.json`:

```json
{
  "named": 1,
  "with_address": 1,
  "with_web_or_ig": 1,
  "comunas": { "Providencia": 1 }
}
```

No son datos reales de Santiago; solo prueban que `summarize` cuenta bien.

## Decisión

**OSM se descarta por ahora.** No se pudo medir su cobertura real y el criterio
exige datos, no una suposición. Consecuencias:

- `BAILOTECA_SOURCES=seed,search` sigue siendo el valor por defecto.
- `OverpassSource` queda implementado pero desactivado; se puede activar con
  `BAILOTECA_SOURCES=seed,search,osm` cuando haya red.
- No se bloquea ninguna otra tarea.

## Cómo reevaluar

Con red disponible:

```bash
.venv/bin/python -m bailoteca spike
```

Si el resultado trae ≥10 academias con nombre y al menos dirección o
web/Instagram, actualizar este documento, agregar `osm` al valor por defecto de
`BAILOTECA_SOURCES` y correr `bailoteca run --dry-run` para revisar la calidad antes de
proponer.
