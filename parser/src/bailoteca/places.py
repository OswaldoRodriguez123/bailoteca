"""Enriquecimiento con Google Maps vía SerpApi (rating, reseñas, precio, horarios)."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
SERPAPI_URL = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class PlaceInfo:
    place_id: str | None = None
    name: str | None = None
    address: str | None = None
    rating: float | None = None
    reviews: int | None = None
    price: str | None = None
    hours: dict[str, str] | None = None
    open_state: str | None = None
    maps_url: str | None = None
    thumbnail: str | None = None
    phone: str | None = None
    website: str | None = None
    place_type: str | None = None
    gps_coordinates: dict | None = None
    raw: dict | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def clean_name(name: str | None) -> str:
    if not name:
        return ""
    # Google suele indexar el nombre comercial sin el texto promocional.
    for separator in ("|", "(", "@"):
        if separator in name:
            name = name.split(separator, 1)[0]
    return " ".join(name.split())



def _unaccent(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )


def _query_variants(
    name: str,
    comuna: str | None,
    address: str | None,
) -> list[str]:
    cleaned = clean_name(name)
    base = cleaned or (name or "").strip()
    variants: list[str] = []
    combos = []
    if address:
        combos.append([base, address])
    if comuna:
        combos.append([base, comuna])
        for extra in ("academia de baile", "clases de baile", "danza", "estudio"):
            combos.append([base, extra, comuna])
    combos.append([base])
    combos.append([base, "academia de baile"])
    combos.append([base, "estudio de danza"])
    combos.append([base, "clases de baile"])
    # Búsquedas más amplias por si la comuna no coincide con Google.
    combos.append([base, "Chile"])
    combos.append([base, "Santiago", "Chile"])
    for combo in combos:
        parts = [p for p in combo if p]
        if comuna and comuna.lower() not in " ".join(parts).lower():
            parts = parts + [comuna]
        if "chile" not in " ".join(parts).lower():
            parts = parts + ["Chile"]
        variants.append(" ".join(parts))
    # Versión sin acentos como respaldo.
    extra = [_unaccent(v) for v in variants if _unaccent(v) != v]
    variants.extend(extra)
    # Deduplicar manteniendo orden.
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique

def _in_chile(item: dict) -> bool:
    """Verifica que el resultado de SerpApi sea de Chile (evita falsos positivos extranjeros)."""
    gps = item.get("gps_coordinates")
    if isinstance(gps, dict):
        try:
            lat = float(gps.get("latitude"))
            lng = float(gps.get("longitude"))
        except (TypeError, ValueError):
            lat = lng = None
        if lat is not None and lng is not None:
            # Bounding box aproximado de Chile continental.
            if not (-56.0 <= lat <= -17.0 and -76.0 <= lng <= -66.0):
                return False
    address = (item.get("address") or "").lower()
    # Rechazar si la dirección menciona un país extranjero conocido.
    foreign = (
        "panama", "panamá", "peru", "perú", "argentina", "colombia",
        "mexico", "méxico", "españa", "spain", "venezuela", "ecuador",
        "bolivia", "uruguay", "paraguay", "brasil", "brazil",
    )
    if any(country in address for country in foreign):
        return False
    phone = (item.get("phone") or "").lower()
    # Prefijos telefónicos extranjeros comunes.
    if phone.startswith("+") and not phone.startswith("+56"):
        return False
    return True


def _pick_result(results: list[dict], name: str, comuna: str | None) -> dict | None:
    if not results:
        return None
    clean = clean_name(name).lower()
    name_l = (name or "").lower()
    comuna_l = (comuna or "").lower()
    best = None
    best_score = -1
    for item in results:
        if not _in_chile(item):
            continue
        title = (item.get("title") or "").lower()
        address = (item.get("address") or "").lower()
        score = 0
        if clean and (clean in title or title in clean):
            score += 3
        elif name_l and (name_l in title or title in name_l):
            score += 2
        # Coincidencia por palabras significativas del nombre.
        if clean:
            words = [w for w in clean.split() if len(w) > 3]
            if words and all(word in title for word in words[:2]):
                score += 1
        if comuna_l and comuna_l in address:
            score += 1
        # Similitud a nivel de tokens para nombres comerciales
        # (Mambo Roakes ~ Mambo Rock), evitando falsos positivos como
        # Mambo Roakes ~ Mambo Madness.
        if clean:
            clean_tokens = [t for t in clean.split() if len(t) >= 4]
            title_tokens = title.split()
            matched_tokens = 0
            for ct in clean_tokens:
                if any(ct == tt for tt in title_tokens):
                    matched_tokens += 1
                    continue
                if any(
                    len(tt) >= 4
                    and SequenceMatcher(None, ct, tt).ratio() >= 0.7
                    for tt in title_tokens
                ):
                    matched_tokens += 1
            if clean_tokens and matched_tokens:
                score += 2 * matched_tokens
                if matched_tokens == len(clean_tokens):
                    score += 1
        if score > best_score:
            best_score = score
            best = item
    # Si ningún resultado se parece al nombre, no tomar uno arbitrario.
    threshold = 2 if comuna_l else 1
    if best is None or best_score < threshold:
        return None
    return best


def parse_place(data: dict, name: str, comuna: str | None) -> PlaceInfo | None:
    results = data.get("local_results")
    if not isinstance(results, list) or not results:
        return None
    item = _pick_result(results, name, comuna)
    if not isinstance(item, dict):
        return None
    place_id = item.get("place_id")
    address = item.get("address")
    maps_url = None
    if place_id:
        maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    thumbnail = item.get("thumbnail") or item.get("serpapi_thumbnail")
    phone = item.get("phone")
    website = item.get("website")
    place_type = item.get("type")
    gps_coordinates = item.get("gps_coordinates")
    if not isinstance(gps_coordinates, dict):
        gps_coordinates = None
    hours = item.get("operating_hours")
    if not isinstance(hours, dict):
        hours = None
    try:
        rating = float(item.get("rating")) if item.get("rating") is not None else None
    except (TypeError, ValueError):
        rating = None
    try:
        reviews = int(item.get("reviews")) if item.get("reviews") is not None else None
    except (TypeError, ValueError):
        reviews = None
    return PlaceInfo(
        place_id=place_id,
        name=item.get("title"),
        address=address,
        rating=rating,
        reviews=reviews,
        price=item.get("price"),
        hours=hours,
        open_state=item.get("open_state"),
        maps_url=maps_url,
        thumbnail=thumbnail,
        phone=phone,
        website=website,
        place_type=place_type,
        gps_coordinates=gps_coordinates,
        raw=item,
    )


def fetch_place(
    name: str,
    comuna: str | None,
    address: str | None,
    lat: float | None,
    lng: float | None,
    http: Any,
    api_key: str,
    timeout: float = 10.0,
) -> PlaceInfo | None:
    variants = _query_variants(name, comuna, address)
    for query in variants:
        params: dict[str, str] = {
            "engine": "google_maps",
            "type": "search",
            "q": query,
            "api_key": api_key,
            "gl": "cl",
            "hl": "es",
        }
        if lat is not None and lng is not None:
            params["ll"] = f"@{lat},{lng},14z"
        try:
            response = http.get(SERPAPI_URL, params=params, timeout=timeout)
        except Exception:
            continue
        if getattr(response, "status_code", 0) != 200:
            continue
        try:
            data = response.json()
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        info = parse_place(data, name, comuna)
        if info is not None:
            return info
    return None


def to_dict(info: PlaceInfo) -> dict:
    return {
        "google": {
            "place_id": info.place_id,
            "name": info.name,
            "address": info.address,
            "rating": info.rating,
            "reviews": info.reviews,
            "price": info.price,
            "hours": info.hours,
            "open_state": info.open_state,
            "maps_url": info.maps_url,
            "thumbnail": info.thumbnail,
            "phone": info.phone,
            "website": info.website,
            "type": info.place_type,
            "gps_coordinates": info.gps_coordinates,
            "raw": info.raw,
            "fetched_at": info.fetched_at.isoformat()
            if info.fetched_at is not None
            else None,
        }
    }