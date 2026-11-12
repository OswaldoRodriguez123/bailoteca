"""Convivencia de providers de búsqueda web.

`CombinedSearchSource` consulta varias fuentes en orden, descarta URLs
repetidas y sigue con la siguiente fuente si una falla o no responde.
`build_search_source` centraliza la construcción de cada provider para que el
descubrimiento (`run`) y la Pasada B de sedes usen la misma configuración.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from bailoteca.config import Config
from bailoteca.models import Candidate


class Source(Protocol):
    name: str

    def discover(self) -> list[Candidate]: ...


class CombinedSearchSource:
    """Consulta varias fuentes y devuelve candidatos únicos, en orden."""

    name = "combined"

    def __init__(self, sources: Iterable[Source | None]):
        self.sources = [source for source in sources if source is not None]

    def __bool__(self) -> bool:
        return bool(self.sources)

    def discover(self) -> list[Candidate]:
        seen: set[str] = set()
        candidates: list[Candidate] = []
        for source in self.sources:
            try:
                found = source.discover() or []
            except Exception:
                continue
            for candidate in found:
                key = (candidate.url or candidate.handle or candidate.name or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)
        return candidates


def build_search_source(
    kind: str,
    queries: list[str],
    config: Config,
    http=None,
    num: int | None = None,
    delay: float | None = None,
) -> Source | None:
    """Construye la fuente `kind`; None si no hay key o el kind no existe."""

    import httpx

    client = http or httpx.Client(timeout=10)
    if kind == "brave":
        if not config.brave_api_key:
            return None
        from bailoteca.sources.brave import BraveSource

        kwargs = {"delay": delay} if delay is not None else {}
        if num is not None:
            kwargs["num"] = num
        return BraveSource(queries, api_key=config.brave_api_key, http=client, **kwargs)
    if kind == "tinyfish":
        if not config.tinyfish_api_key:
            return None
        from bailoteca.sources.tinyfish import TinyFishSource

        kwargs = {"delay": delay} if delay is not None else {}
        return TinyFishSource(queries, api_key=config.tinyfish_api_key, http=client, **kwargs)
    if kind == "serpapi":
        if not config.serpapi_key:
            return None
        from bailoteca.sources.serpapi import SerpApiSource

        kwargs = {}
        if delay is not None:
            kwargs["delay"] = delay
        if num is not None:
            kwargs["num"] = num
        return SerpApiSource(
            queries,
            api_key=config.serpapi_key,
            http=client,
            cache_dir=config.cache_dir,
            **kwargs,
        )
    return None


def build_search_sources(
    kinds: list[str],
    queries: list[str],
    config: Config,
    http=None,
    num: int | None = None,
    delay: float | None = None,
) -> CombinedSearchSource:
    """Combina los providers disponibles en una sola fuente."""

    return CombinedSearchSource(
        build_search_source(kind, queries, config, http=http, num=num, delay=delay)
        for kind in kinds
    )
