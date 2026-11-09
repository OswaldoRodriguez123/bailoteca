from __future__ import annotations

import json
from typing import Protocol

from bailoteca.models import Candidate
from bailoteca.normalize import normalize_handle

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
GRAN_SANTIAGO_BBOX = (-33.65, -70.85, -33.30, -70.50)

QUERY_TEMPLATE = """
[out:json][timeout:25];
(
  node["amenity"="dancing_school"]({s},{w},{n},{e});
  way["amenity"="dancing_school"]({s},{w},{n},{e});
  node["leisure"="dance"]({s},{w},{n},{e});
  way["leisure"="dance"]({s},{w},{n},{e});
  node["sport"="dancing"]({s},{w},{n},{e});
  way["sport"="dancing"]({s},{w},{n},{e});
);
out center tags;
"""


class HttpClient(Protocol):
    def post(self, url: str, content: str): ...


def parse_overpass(data: dict) -> list[Candidate]:
    candidates: list[Candidate] = []
    for element in data.get("elements", []):
        tags = element.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        street = (tags.get("addr:street") or "").strip()
        number = (tags.get("addr:housenumber") or "").strip()
        address = " ".join(part for part in (street, number) if part) or None
        comuna = (tags.get("addr:city") or "").strip() or None
        url = tags.get("website") or tags.get("contact:website")
        handle = normalize_handle(tags.get("contact:instagram"))
        center = element.get("center") or {}
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        candidates.append(
            Candidate(
                name=name,
                url=url,
                handle=handle,
                source="osm",
                comuna=comuna,
                raw={
                    "address": address,
                    "comuna": comuna,
                    "lat": lat,
                    "lon": lon,
                },
            )
        )
    return candidates


def build_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    return QUERY_TEMPLATE.format(s=south, w=west, n=north, e=east)


class OverpassSource:
    name = "osm"

    def __init__(
        self,
        bbox: tuple[float, float, float, float] = GRAN_SANTIAGO_BBOX,
        http: HttpClient | None = None,
    ):
        self.bbox = bbox
        self.http = http

    def discover(self) -> list[Candidate]:
        if self.http is None:
            import httpx

            http: HttpClient = httpx
        else:
            http = self.http
        query = build_query(self.bbox)
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                response = http.post(endpoint, content=query)
            except Exception:
                continue
            if getattr(response, "status_code", 0) != 200:
                continue
            try:
                return parse_overpass(response.json())
            except (ValueError, json.JSONDecodeError):
                continue
        return []
