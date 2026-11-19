from __future__ import annotations

import json
from difflib import SequenceMatcher
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
SERPAPI_URL = "https://serpapi.com/search.json"
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

# Mapeo priceLevel (Places API New) -> símbolos estilo SerpApi.
PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": "Gratis",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}

# Días de la semana en inglés (clave usada por Places API) -> clave estable.
_DAY_KEYS = {
    "monday": "monday",
    "tuesday": "tuesday",
    "wednesday": "wednesday",
    "thursday": "thursday",
    "friday": "friday",
    "saturday": "saturday",
    "sunday": "sunday",
}


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

FOREIGN_COUNTRIES = (
    "panama", "panamá", "peru", "perú", "argentina", "colombia",
    "mexico", "méxico", "españa", "spain", "venezuela", "ecuador",
    "bolivia", "uruguay", "paraguay", "brasil", "brazil",
)
# Bounding box aproximado de Chile continental: (sur, oeste, norte, este).
CHILE_BBOX = (-56.0, -76.0, -17.0, -66.0)


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
            south, west, north, east = CHILE_BBOX
            if not (south <= lat <= north and west <= lng <= east):
                return False
    address = (item.get("address") or "").lower()
    # Rechazar si la dirección menciona un país extranjero conocido.
    if any(country in address for country in FOREIGN_COUNTRIES):
        return False
    phone = (item.get("phone") or "").lower()
    # Prefijos telefónicos extranjeros comunes.
    if phone.startswith("+") and not phone.startswith("+56"):
        return False
    return True


GENERIC_TOKENS = {
    "academia", "academias", "baile", "bailes", "clases", "clase",
    "danza", "danzas", "estudio", "estudios", "chile", "santiago",
    "danza", "danzas",
}


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
        # Rechazar si ningún token distintivo del nombre coincide con el título.
        # Evita falsos positivos como "Academia Solar" -> "Academia de Baile Baila Conmigo".
        distinctive = [t for t in clean.split() if len(t) >= 4 and t not in GENERIC_TOKENS]
        if not distinctive:
            distinctive = [t for t in clean.split() if len(t) >= 4]
        title_token_list = title.split()
        distinctive_match = False
        collapsed_title = "".join(title_token_list)
        for dt in distinctive:
            if any(dt == tt for tt in title_token_list):
                distinctive_match = True
                break
            # Nombres pegados en Google ("BailemosTodos"), tokens de 6+ letras.
            if len(dt) >= 6 and dt in collapsed_title:
                distinctive_match = True
                break
        if distinctive and not distinctive_match:
            continue
        # Similitud a nivel de tokens para nombres comerciales
        # (Mambo Roakes ~ Mambo Madness), evitando falsos positivos como
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


def _place_title(item: dict) -> str:
    dn = item.get("displayName")
    if isinstance(dn, dict):
        return dn.get("text") or ""
    if isinstance(dn, str):
        return dn
    return item.get("name") or ""


def _place_address(item: dict) -> str | None:
    return item.get("formattedAddress") or item.get("shortFormattedAddress")


def _place_gps(item: dict) -> dict | None:
    loc = item.get("location")
    if isinstance(loc, dict) and "latitude" in loc and "longitude" in loc:
        try:
            return {"latitude": float(loc["latitude"]), "longitude": float(loc["longitude"])}
        except (TypeError, ValueError):
            return None
    return None


def _hours_from_places(item: dict) -> dict[str, str] | None:
    roh = item.get("regularOpeningHours")
    if not isinstance(roh, dict):
        return None
    descs = roh.get("weekdayDescriptions")
    if not isinstance(descs, list) or not descs:
        return None
    hours: dict[str, str] = {}
    for desc in descs:
        if not isinstance(desc, str):
            continue
        # Formato típico: "Monday: 9:00 AM – 5:00 PM" o "Monday: Closed".
        if ":" in desc:
            day, _, rest = desc.partition(":")
            day_key = day.strip().lower()
            value = rest.strip()
            if day_key and value:
                hours[day_key] = value
    return hours or None


def _pick_result_google(places: list[dict], name: str, comuna: str | None) -> dict | None:
    if not places:
        return None
    clean = clean_name(name).lower()
    name_l = (name or "").lower()
    comuna_l = (comuna or "").lower()
    best = None
    best_score = -1
    for item in places:
        gps = _place_gps(item)
        # Filtro Chile por bbox si hay coordenadas.
        if gps:
            south, west, north, east = CHILE_BBOX
            lat, lng = gps["latitude"], gps["longitude"]
            if not (south <= lat <= north and west <= lng <= east):
                continue
        address = (_place_address(item) or "").lower()
        if any(country in address for country in FOREIGN_COUNTRIES):
            continue
        title = _place_title(item).lower()
        score = 0
        if clean and (clean in title or title in clean):
            score += 3
        elif name_l and (name_l in title or title in name_l):
            score += 2
        if clean:
            words = [w for w in clean.split() if len(w) > 3]
            if words and all(word in title for word in words[:2]):
                score += 1
        if comuna_l and comuna_l in address:
            score += 1
        distinctive = [t for t in clean.split() if len(t) >= 4 and t not in GENERIC_TOKENS]
        if not distinctive:
            distinctive = [t for t in clean.split() if len(t) >= 4]
        title_token_list = title.split()
        distinctive_match = False
        collapsed_title = "".join(title_token_list)
        for dt in distinctive:
            if any(dt == tt for tt in title_token_list):
                distinctive_match = True
                break
            if len(dt) >= 6 and dt in collapsed_title:
                distinctive_match = True
                break
        if distinctive and not distinctive_match:
            continue
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
    threshold = 2 if comuna_l else 1
    if best is None or best_score < threshold:
        return None
    return best


def parse_place_google(data: dict, name: str, comuna: str | None) -> PlaceInfo | None:
    places = data.get("places")
    if not isinstance(places, list) or not places:
        return None
    item = _pick_result_google(places, name, comuna)
    if not isinstance(item, dict):
        return None
    place_id = item.get("id")
    address = _place_address(item)
    maps_url = item.get("googleMapsUri")
    phone = item.get("internationalPhoneNumber") or item.get("nationalPhoneNumber")
    website = item.get("websiteUri")
    place_type = item.get("primaryType")
    gps = _place_gps(item)
    hours = _hours_from_places(item)
    open_state = None
    roh = item.get("regularOpeningHours")
    if isinstance(roh, dict) and "openNow" in roh:
        open_state = "Open now" if roh.get("openNow") else "Closed"
    cur = item.get("currentOpeningHours")
    if isinstance(cur, dict) and "openNow" in cur and open_state is None:
        open_state = "Open now" if cur.get("openNow") else "Closed"
    try:
        rating = float(item.get("rating")) if item.get("rating") is not None else None
    except (TypeError, ValueError):
        rating = None
    try:
        reviews = int(item.get("userRatingCount")) if item.get("userRatingCount") is not None else None
    except (TypeError, ValueError):
        reviews = None
    price = PRICE_LEVEL_MAP.get(item.get("priceLevel")) if isinstance(item.get("priceLevel"), str) else None
    if price is None and isinstance(item.get("priceLevel"), str):
        price = item.get("priceLevel")
    # Thumbnail: Places API (New) requiere un fetch adicional con la key;
    # lo omitimos (la cover ya se gestiona por refresh-images). Si en el
    # futuro se quiere, construir la URL media con la key.
    thumbnail = None
    return PlaceInfo(
        place_id=place_id,
        name=_place_title(item) or None,
        address=address,
        rating=rating,
        reviews=reviews,
        price=price,
        hours=hours,
        open_state=open_state,
        maps_url=maps_url,
        thumbnail=thumbnail,
        phone=phone,
        website=website,
        place_type=place_type,
        gps_coordinates=gps,
        raw=item,
    )


def fetch_place_google(
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
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.rating,"
        "places.userRatingCount,places.priceLevel,places.regularOpeningHours,"
        "places.currentOpeningHours,places.googleMapsUri,places.photos,"
        "places.nationalPhoneNumber,places.internationalPhoneNumber,"
        "places.websiteUri,places.primaryType,places.location"
    )
    for query in variants:
        body: dict[str, Any] = {"textQuery": query}
        if lat is not None and lng is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 5000.0,
                }
            }
        try:
            response = http.post(
                GOOGLE_PLACES_URL,
                json=body,
                headers={
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": field_mask,
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
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
        info = parse_place_google(data, name, comuna)
        if info is not None:
            return info
    return None
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
