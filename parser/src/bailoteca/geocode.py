"""Geocodificación de sedes (``academy_locations``) para el orden por cercanía.

Dos fuentes, en orden de preferencia:

1. ``google.gps_coordinates`` ya guardado en la academia — **solo cuando la
   academia tiene exactamente una sede** (con varias sedes no se puede saber
   cuál corresponde). Sin HTTP.
2. Nominatim (OpenStreetMap) como respaldo, **solo si la sede tiene una
   dirección de calle**; nunca se geocodifica solo una comuna (sería un
   centroide). Una petición a la vez, con ``delay`` segundos entre peticiones.

Por defecto (dry-run) solo devuelve el plan; con ``apply=True`` escribe
``lat``/``lng`` en las filas resueltas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

USER_AGENT = "Bailoteca/1.0 (+https://bailoteca.cl)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

LOCATIONS_QUERY = """
select al.id::text as location_id,
       a.slug as academy_slug,
       al.address,
       al.comuna,
       (select count(*) from academy_locations x where x.academy_id = a.id) as sede_count,
       (a.google->'gps_coordinates'->>'latitude')::float as google_lat,
       (a.google->'gps_coordinates'->>'longitude')::float as google_lng
from academy_locations al
join academies a on a.id = al.academy_id
where al.lat is null or al.lng is null
order by a.name asc, al.label nulls first
"""

UPDATE_LOCATION_SQL = """
update academy_locations set lat = %s, lng = %s where id = %s
"""

_LOCATIONS_KEYS = (
    "location_id",
    "academy_slug",
    "address",
    "comuna",
    "sede_count",
    "google_lat",
    "google_lng",
)


@dataclass(frozen=True)
class GeocodePlan:
    location_id: str
    academy_slug: str
    address: str | None
    lat: float | None
    lng: float | None
    source: str | None  # "google" | "nominatim" | None
    reason: str | None  # None | "sin dirección" | "sin resultado"


def plan(conn) -> list[dict]:
    """Filas candidatas (sedes sin coordenadas) como dicts."""
    raw_rows = conn.execute(LOCATIONS_QUERY).fetchall()
    rows: list[dict] = []
    for row in raw_rows:
        if isinstance(row, dict):
            rows.append(dict(row))
        else:
            rows.append(dict(zip(_LOCATIONS_KEYS, row)))
    return rows


def nominatim_search(
    query: str, client, timeout: float = 10.0
) -> tuple[float, float] | None:
    """Primera coincidencia de Nominatim para ``query``; None ante cualquier fallo."""
    try:
        resp = client.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "cl",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        return None


def run(
    conn,
    client,
    apply: bool = False,
    delay: float = 1.1,
    sleep=time.sleep,
) -> list[GeocodePlan]:
    """Decide la fuente de coordenadas por sede.

    Orden por fila: (1) una sola sede y ambas coordenadas de Google presentes →
    ``google``, sin HTTP; (2) sin dirección de calle → ``sin dirección``, sin
    HTTP; (3) Nominatim con ``address, comuna, Chile``, durmiendo ``delay``
    antes de cada petición tras la primera; sin resultado → ``sin resultado``.
    Con ``apply`` actualiza solo las filas resueltas; si no, solo reporta.
    """

    plans: list[GeocodePlan] = []
    requests = 0
    for row in plan(conn):
        location_id = row["location_id"]
        slug = row.get("academy_slug")
        address = row.get("address")
        comuna = row.get("comuna")
        google_lat = row.get("google_lat")
        google_lng = row.get("google_lng")
        sede_count = row.get("sede_count") or 0

        if sede_count == 1 and google_lat is not None and google_lng is not None:
            plans.append(
                GeocodePlan(
                    location_id, slug, address, google_lat, google_lng,
                    "google", None,
                )
            )
            continue
        if not address:
            plans.append(
                GeocodePlan(
                    location_id, slug, address, None, None,
                    None, "sin dirección",
                )
            )
            continue
        if requests:
            sleep(delay)
        query = ", ".join(filter(None, [address, comuna, "Chile"]))
        coords = nominatim_search(query, client)
        requests += 1
        if coords is None:
            plans.append(
                GeocodePlan(
                    location_id, slug, address, None, None,
                    None, "sin resultado",
                )
            )
        else:
            plans.append(
                GeocodePlan(
                    location_id, slug, address, coords[0], coords[1],
                    "nominatim", None,
                )
            )

    if apply:
        for item in plans:
            if item.source is None:
                continue
            conn.execute(
                UPDATE_LOCATION_SQL,
                (item.lat, item.lng, item.location_id),
            )
    return plans
