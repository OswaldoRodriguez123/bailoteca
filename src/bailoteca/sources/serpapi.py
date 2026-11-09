"""Descubrimiento vía SerpApi (Google Search JSON).

Evita el bloqueo anti-bot de DuckDuckGo HTML. Requiere SERPAPI_KEY
(250 req/mes gratis en el plan free según maps-gluten-rag).
"""

from __future__ import annotations

import time

from typing import Protocol
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.sources.search import INSTAGRAM_POST_PREFIXES

SERPAPI_URL = "https://serpapi.com/search.json"


class HttpClient(Protocol):
    def get(self, url: str, params: dict | None = None): ...


def parse_serpapi_json(data: dict) -> list[Candidate]:
    """Convierte la respuesta JSON de SerpApi en candidatos."""
    candidates: list[Candidate] = []
    for item in data.get("organic_results", []):
        if not isinstance(item, dict):
            continue
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue
        if not url.startswith(("http://", "https://")):
            continue
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host == "instagram.com" and parts.path.startswith(INSTAGRAM_POST_PREFIXES):
            continue
        handle = None
        if host == "instagram.com":
            # Perfil: /@handle o /handle
            handle = parts.path.strip("/").split("/")[0].lstrip("@") or None
        candidates.append(
            Candidate(name=title, url=url, handle=handle, source="serpapi")
        )
    return candidates


class SerpApiSource:
    name = "serpapi"

    def __init__(
        self,
        queries: list[str],
        api_key: str | None,
        http: HttpClient,
        delay: float = 0.5,
        timeout: float = 10.0,
        num: int = 10,
    ):
        self.queries = queries
        self.api_key = api_key
        self.http = http
        self.delay = delay
        self.timeout = timeout
        self.num = num

    def discover(self) -> list[Candidate]:
        if not self.api_key:
            return []
        candidates: list[Candidate] = []
        last_request: float | None = None
        for query in self.queries:
            if last_request is not None:
                wait = self.delay - (time.monotonic() - last_request)
                if wait > 0:
                    time.sleep(wait)
            last_request = time.monotonic()
            try:
                response = self.http.get(
                    SERPAPI_URL,
                    params={
                        "q": query,
                        "api_key": self.api_key,
                        "engine": "google",
                        "gl": "cl",
                        "hl": "es",
                        "num": str(self.num),
                        "safe": "active",
                    },
                    timeout=self.timeout,
                )
            except Exception:
                continue
            if response.status_code != 200:
                continue
            try:
                data = response.json()
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            candidates.extend(parse_serpapi_json(data))
        return candidates
