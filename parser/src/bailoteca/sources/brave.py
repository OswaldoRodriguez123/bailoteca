"""Descubrimiento vía Brave Search API (gratuita).

Evita el bloqueo anti-bot de DuckDuckGo HTML desde IPs de datacenter.
Requiere BRAVE_API_KEY (plan free con registro en api.search.brave.com).
"""

from __future__ import annotations

import time

from typing import Protocol
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.sources.search import INSTAGRAM_POST_PREFIXES, SEARCH_DOMAINS

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class HttpClient(Protocol):
    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float | None = None): ...


def parse_brave_json(data: dict) -> list[Candidate]:
    """Convierte la respuesta JSON de Brave en candidatos."""
    candidates: list[Candidate] = []
    web = data.get("web")
    results = web.get("results") if isinstance(web, dict) else None
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
        candidates.append(
            Candidate(name=title, url=url, handle=handle, source="brave")
        )
    return candidates


class BraveSource:
    name = "brave"

    def __init__(
        self,
        queries: list[str],
        api_key: str | None,
        http: HttpClient,
        delay: float = 1.0,
        timeout: float = 10.0,
        num: int = 20,
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
        headers = {"X-Subscription-Token": self.api_key}
        candidates: list[Candidate] = []
        last_request: float | None = None
        for query in self.queries:
            params = {
                "q": query,
                "count": str(self.num),
                "country": "cl",
                "search_lang": "es",
                "safesearch": "moderate",
            }
            if last_request is not None:
                wait = self.delay - (time.monotonic() - last_request)
                if wait > 0:
                    time.sleep(wait)
            last_request = time.monotonic()
            try:
                response = self.http.get(
                    BRAVE_URL,
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
            candidates.extend(parse_brave_json(data))
        return candidates
