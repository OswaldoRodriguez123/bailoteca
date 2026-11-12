"""Triage de país: señales locales (.cl, +56, comuna chilena) y geo-confirmación
OSM/Overpass, siempre consultivo. Nunca bloquea publicación ni escribe en la base.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from bailoteca.places import CHILE_BBOX, FOREIGN_COUNTRIES
from bailoteca_shared.regions import region_slug_for_comuna

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
)
USER_AGENT = "Bailoteca/1.0 (+https://github.com/OswaldoRodriguez123/bailoteca)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
OVERPASS_TIMEOUT = 15.0
MAX_HITS = 10

_VERDICT_CHILE = "chile"
_VERDICT_EXTRANJERA = "extranjera"

_CL_URL_RE = re.compile(r"\.cl(?:/|[:?#]|$)")
_NON_PLUS_DIGIT_RE = re.compile(r"[^0-9+]")
_TEL_PREFIX_RE = re.compile(r"^(tel:)", re.I)


@dataclass(frozen=True)
class AcademySnapshot:
    name: str
    urls: tuple[str, ...] = ()
    phones: tuple[str, ...] = ()
    # SOLO google.address + locations[].address: descripción y estilos son señal
    # de contenido (p. ej. «danzas españolas»), no de ubicación.
    address_texts: tuple[str, ...] = ()
    comuna: str | None = None


@dataclass(frozen=True)
class CountryVerdict:
    verdict: str  # "chile" | "extranjera" | "sin_huella"
    reasons: tuple[str, ...]


def sanitize_osm_name(name: str) -> str:
    """Elimina caracteres peligrosos para Overpass QL y colapsa espacios."""
    cleaned = re.sub(r'["\\]', "", name)
    return " ".join(cleaned.split())


def _phone_parts(raw: str) -> str:
    p = _TEL_PREFIX_RE.sub("", (raw or "").strip())
    had_plus = p.startswith("+")
    p = _NON_PLUS_DIGIT_RE.sub("", p)
    return ("+" if had_plus else "") + p.lstrip("+")


def local_points(snap: AcademySnapshot) -> tuple[int, tuple[str, ...]]:
    points = 0
    reasons: list[str] = []

    chile_url = False
    for u in snap.urls:
        u = (u or "").lower()
        if u.startswith(("mailto:", "tel:")):
            continue
        if _CL_URL_RE.search(u):
            chile_url = True
            break
    if chile_url:
        points += 1
        reasons.append("sitio .cl")

    chile_phone = False
    foreign_phone_reason: str | None = None
    for raw in snap.phones:
        p = _phone_parts(raw)
        if len(p) < 8:
            continue
        if p.startswith("+56") or (not p.startswith("+") and p.startswith("56") and len(p) >= 10):
            chile_phone = True
        elif p.startswith("+"):
            foreign_phone_reason = foreign_phone_reason or f"teléfono internacional: {p[:5]}"
        elif not p.startswith("+") and len(p) >= 11 and not p.startswith("56"):
            foreign_phone_reason = foreign_phone_reason or f"teléfono internacional: {p[:4]}"

    if chile_phone:
        points += 1
        reasons.append("teléfono +56")
    if foreign_phone_reason:
        points -= 2
        reasons.append(foreign_phone_reason)

    foreign_token: str | None = None
    for text in snap.address_texts:
        lowered = (text or "").lower()
        for token in FOREIGN_COUNTRIES:
            if token in lowered:
                foreign_token = foreign_token or token
                break
    if foreign_token:
        points -= 2
        reasons.append(f"país en dirección: {foreign_token}")

    if region_slug_for_comuna(snap.comuna) is not None:
        points += 1
        reasons.append(f"comuna chilena: {(snap.comuna or '').strip().lower()}")

    return points, tuple(reasons)


def _local_verdict(points: int, chile_explicit: bool, foreign_strong: bool) -> str:
    if foreign_strong:
        return "sin_huella" if chile_explicit else "extranjera"
    if points >= 2:
        return "chile"
    if points <= -1:
        return "extranjera"
    return "sin_huella"


def _finish(verdict: str, reasons: list[str]) -> CountryVerdict:
    if verdict == "sin_huella" and not reasons:
        reasons = ["sin señales claras"]
    return CountryVerdict(verdict, tuple(reasons))


def fetch_overpass(
    name: str,
    *,
    client: Any | None = None,
    timeout: float = OVERPASS_TIMEOUT,
) -> list[dict] | None:
    """Consulta global por nombre exacto (case-insensitive). None ante red/timeout."""
    sanitized = sanitize_osm_name(name or "")
    if not sanitized:
        return []
    escaped = re.escape(sanitized)
    query = f'[out:json][timeout:10]; nwr["name"~"^{escaped}$",i]; out center tags;'
    owns_client = client is None
    try:
        http = client or httpx.Client(headers=REQUEST_HEADERS, timeout=timeout)
    except Exception:
        return None
    try:
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                response = http.post(endpoint, content=query)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and isinstance(data.get("elements"), list):
                    return list(data["elements"])[:MAX_HITS]
                # Respuesta 200 pero sin `elements`: tratamos OSM como "sin
                # respuesta" — una forma que no entendemos jamás debe leerse
                # como "no hay homónimos en OSM".
                return None
            except Exception:
                time.sleep(1.0)
                continue
        return None
    finally:
        if owns_client:
            try:
                http.close()
            except Exception:
                pass


def classify_overpass_hits(hits: list[dict]) -> tuple[int, int]:
    """(chile_hits, foreign_hits). Hits sin país ni coords reconocidas se ignoran."""
    chile = 0
    foreign = 0
    south, west, north, east = CHILE_BBOX
    for hit in hits or []:
        tags = hit.get("tags") or {}
        country = str(tags.get("addr:country") or "").strip().lower()
        if country in {"cl", "chile"}:
            chile += 1
            continue
        if country:
            foreign += 1
            continue
        lat = hit.get("lat")
        lon = hit.get("lon")
        center = hit.get("center") or {}
        if lat is None:
            lat = center.get("lat")
        if lon is None:
            lon = center.get("lon")
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        if south <= lat_f <= north and west <= lon_f <= east:
            chile += 1
        else:
            foreign += 1
    return chile, foreign


def assess(
    snap: AcademySnapshot,
    *,
    skip_osm: bool = False,
    client: Any | None = None,
) -> CountryVerdict:
    points, reason_tuple = local_points(snap)
    reasons = list(reason_tuple)

    chile_explicit = any(
        r == "sitio .cl" or r.startswith("teléfono +56") for r in reasons
    )
    foreign_strong = any(
        r.startswith("teléfono internacional") or r.startswith("país en dirección")
        for r in reasons
    )
    local = _local_verdict(points, chile_explicit, foreign_strong)

    if skip_osm:
        return _finish(local, reasons)

    hits = fetch_overpass(snap.name, client=client)
    if hits is None:
        reasons.append("OSM sin respuesta")
        return _finish(local, reasons)
    chile_hits, foreign_hits = classify_overpass_hits(hits)
    if foreign_hits and not chile_hits:
        reasons.append(f"OSM: {foreign_hits} aparición(es) fuera de Chile")
        return _finish(_VERDICT_EXTRANJERA, reasons)
    if chile_hits and not foreign_hits:
        reasons.append(f"OSM: {chile_hits} aparición(es) en Chile")
        return _finish(_VERDICT_CHILE, reasons)
    return _finish(local, reasons)
