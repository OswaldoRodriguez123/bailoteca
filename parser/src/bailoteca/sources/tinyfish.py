"""Descubrimiento vía TinyFish Search API (gratuita).

Índice distinto al de Brave/SerpApi, útil para encontrar academias que las
otras fuentes no devuelven. Requiere TINYFISH_API_KEY (gratis, sin tarjeta:
https://agent.tinyfish.ai/api-keys).
"""

from __future__ import annotations

import time

from typing import Protocol
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.sources.search import INSTAGRAM_POST_PREFIXES, SEARCH_DOMAINS

TINYFISH_URL = "https://api.search.tinyfish.ai"


class HttpClient(Protocol):
    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float | None = None): ...


def _clean_snippet(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def parse_tinyfish_json(data: dict) -> list[Candidate]:
    """Convierte la respuesta JSON de TinyFish en candidatos."""
    candidates: list[Candidate] = []
    results = data.get("results")
    if not isinstance(results, list):
        return candidates
    for item in results:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue
        if not url.startswith(("http://", "https://")):
            continue
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host in SEARCH_DOMAINS:
            continue
        if host == "instagram.com" and parts.path.startswith(INSTAGRAM_POST_PREFIXES):
            continue
        handle = None
        if host == "instagram.com":
            handle = parts.path.strip("/").split("/")[0].lstrip("@") or None
        snippet = _clean_snippet(item.get("snippet"))
        raw = {"description": snippet} if snippet else {}
        candidates.append(
            Candidate(name=title, url=url, handle=handle, source="tinyfish", raw=raw)
        )
    return candidates


class TinyFishSource:
    name = "tinyfish"

    def __init__(
        self,
        queries: list[str],
        api_key: str | None,
        http: HttpClient,
        delay: float = 1.0,
        timeout: float = 10.0,
    ):
        self.queries = queries
        self.api_key = api_key
        self.http = http
        self.delay = delay
        self.timeout = timeout

    def discover(self) -> list[Candidate]:
        if not self.api_key:
            return []
        headers = {"X-API-Key": self.api_key}
        candidates: list[Candidate] = []
        last_request: float | None = None
        for query in self.queries:
            params = {
                "query": query,
                "location": "CL",
                "language": "es",
            }
            if last_request is not None:
                wait = self.delay - (time.monotonic() - last_request)
                if wait > 0:
                    time.sleep(wait)
            last_request = time.monotonic()
            try:
                response = self.http.get(
                    TINYFISH_URL,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
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
            candidates.extend(parse_tinyfish_json(data))
        return candidates
