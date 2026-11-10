"""Enriquecimiento con Google Maps vía SerpApi (rating, reseñas, precio, horarios)."""

from __future__ import annotations

import json
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
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def clean_name(name: str | None) -> str:
    if not name:
        return ""
    # Google suele indexar el nombre comercial sin el texto promocional.
    for separator in ("|", "(", "@"):
        if separator in name:
            name = name.split(separator, 1)[0]
    return " ".join(name.split())


def _pick_result(results: list[dict], name: str, comuna: str | None) -> dict | None:
    if not results:
        return None
    clean = clean_name(name).lower()
    name_l = (name or "").lower()
    comuna_l = (comuna or "").lower()
    best = None
    best_score = -1
    for item in results:
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
        if score > best_score:
            best_score = score
            best = item
    # Si ningún resultado se parece al nombre, no tomar uno arbitrario.
    if best is None or best_score < 2:
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
    cleaned = clean_name(name)
    query_parts = [cleaned or name]
    if address:
        query_parts.append(address)
    if comuna and comuna.lower() not in " ".join(query_parts).lower():
        query_parts.append(comuna)
    if "chile" not in " ".join(query_parts).lower():
        query_parts.append("Chile")
    params: dict[str, str] = {
        "engine": "google_maps",
        "type": "search",
        "q": " ".join(part for part in query_parts if part).strip(),
        "api_key": api_key,
        "gl": "cl",
        "hl": "es",
    }
    if lat is not None and lng is not None:
        params["ll"] = f"@{lat},{lng},14z"
    try:
        response = http.get(SERPAPI_URL, params=params, timeout=timeout)
    except Exception:
        return None
    if getattr(response, "status_code", 0) != 200:
        return None
    try:
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return parse_place(data, name, comuna)


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
            "fetched_at": info.fetched_at.isoformat()
            if info.fetched_at is not None
            else None,
        }
    }