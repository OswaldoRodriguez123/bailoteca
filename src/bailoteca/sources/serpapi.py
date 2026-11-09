"""Descubrimiento vía SerpApi (Google Search JSON).

Evita el bloqueo anti-bot de DuckDuckGo HTML. Requiere SERPAPI_KEY
(250 req/mes gratis en el plan free según maps-gluten-rag).
"""

from __future__ import annotations

import hashlib
import json
import time

from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.sources.search import INSTAGRAM_POST_PREFIXES

SERPAPI_URL = "https://serpapi.com/search.json"
DEFAULT_CACHE_TTL = 24 * 60 * 60  # 24 h: el cron mensual siempre refresca


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
        cache_dir: Path | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ):
        self.queries = queries
        self.api_key = api_key
        self.http = http
        self.delay = delay
        self.timeout = timeout
        self.num = num
        self.cache_dir = Path(cache_dir) / "serpapi" if cache_dir else None
        self.cache_ttl = cache_ttl

    def _cache_path(self, params: dict) -> Path | None:
        if self.cache_dir is None:
            return None
        cached_params = {k: v for k, v in params.items() if k != "api_key"}
        digest = hashlib.sha256(
            json.dumps(cached_params, sort_keys=True, ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, path: Path) -> dict | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = float(payload["fetched_at"])
            data = payload["data"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        if time.time() - fetched_at > self.cache_ttl:
            return None
        return data

    def _write_cache(self, path: Path, data: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {"fetched_at": time.time(), "data": data}, ensure_ascii=False
                ),
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError:
            pass  # la caché es una optimización: nunca rompe el descubrimiento

    def discover(self) -> list[Candidate]:
        if not self.api_key:
            return []
        candidates: list[Candidate] = []
        last_request: float | None = None
        for query in self.queries:
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "gl": "cl",
                "hl": "es",
                "num": str(self.num),
                "safe": "active",
            }
            cache_path = self._cache_path(params)
            if cache_path is not None:
                cached = self._read_cache(cache_path)
                if cached is not None:
                    candidates.extend(parse_serpapi_json(cached))
                    continue

            if last_request is not None:
                wait = self.delay - (time.monotonic() - last_request)
                if wait > 0:
                    time.sleep(wait)
            last_request = time.monotonic()
            try:
                response = self.http.get(
                    SERPAPI_URL,
                    params=params,
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
            if cache_path is not None:
                self._write_cache(cache_path, data)
            candidates.extend(parse_serpapi_json(data))
        return candidates
