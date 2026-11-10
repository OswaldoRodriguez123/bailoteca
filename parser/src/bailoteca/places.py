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


def _pick_result(results: list[dict], name: str, comuna: str | None) -> dict | None:
    if not results:
        return None
    name_l = (name or "").lower()
    comuna_l = (comuna or "").lower()
    best = None
    best_score = -1
    for item in results:
        title = (item.get("title") or "").lower()
        address = (item.get("address") or "").lower()
        score = 0
        if name_l and (name_l in title or title in name_l):
            score += 2
        if comuna_l and comuna_l in address:
            score += 1
        if score > best_score:
            best_score = score
            best = item
    return best if best is not None else results[0]


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
    params: dict[str, str] = {
        "engine": "google_maps",
        "q": " ".join(part for part in (name, comuna, "Santiago Chile") if part).strip(),
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
        "google_place_id": info.place_id,
        "google_name": info.name,
        "google_address": info.address,
        "google_rating": info.rating,
        "google_reviews": info.reviews,
        "google_price": info.price,
        "google_hours": info.hours,
        "google_open_state": info.open_state,
        "google_maps_url": info.maps_url,
        "google_fetched_at": info.fetched_at,
    }