"""Descarte de candidatos ya conocidos: publicados o en propuestas pendientes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.normalize import normalize_handle, normalize_name

_SOCIAL_HOSTS = {"instagram.com", "facebook.com"}


def _words(value: str | None) -> frozenset[str]:
    return frozenset(normalize_name(value or "").split())


def url_parts(url: str):
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return None
    host = (parts.hostname or "").lower().removeprefix("www.")
    if not host or not parts.scheme.startswith("http"):
        return None
    return host, parts.path or "/"


def canonical_url(url: str | None) -> str | None:
    parsed = url_parts(url or "")
    if parsed is None:
        return None
    host, path = parsed
    clean_path = path.rstrip("/") or "/"
    return f"https://{host}{clean_path.lower()}"


def extract_handle(url: str) -> str | None:
    parsed = url_parts(url)
    if parsed is None:
        return None
    host, path = parsed
    if host not in _SOCIAL_HOSTS:
        return None
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return None
    handle = normalize_handle(segments[0])
    return handle or None


@dataclass(frozen=True)
class ExistingIndex:
    names: tuple[frozenset[str], ...] = field(default_factory=tuple)
    urls: frozenset[str] = frozenset()
    handles: frozenset[str] = frozenset()


def _iter_links(entry: dict) -> Iterable[dict]:
    if isinstance(entry.get("links"), list):
        yield from entry["links"]
        return
    for kind in ("web", "instagram", "facebook", "tiktok", "whatsapp", "phone", "email"):
        value = entry.get(kind)
        if isinstance(value, str):
            yield {"kind": kind, "url": value}
        elif isinstance(value, list):
            for url in value:
                yield {"kind": kind, "url": url}


def build_existing_index(
    published: list[dict],
    pending: list[dict],
) -> ExistingIndex:
    names: list[frozenset[str]] = []
    urls: set[str] = set()
    handles: set[str] = set()
    for entry in list(published) + list(pending):
        words = _words(entry.get("name"))
        if words:
            names.append(words)
        for link in _iter_links(entry):
            host = url_parts(link.get("url") or "")
            if host is None:
                continue
            handle = extract_handle(link["url"])
            if handle:
                handles.add(handle)
            canon = canonical_url(link["url"])
            if canon:
                urls.add(canon)
    return ExistingIndex(
        names=tuple(names),
        urls=frozenset(urls),
        handles=frozenset(handles),
    )


def is_duplicate(candidate: Candidate, index: ExistingIndex) -> bool:
    cand_words = _words(candidate.name)
    if cand_words and index.names:
        for words in index.names:
            if not words:
                continue
            shorter, longer = (
                (words, cand_words) if len(words) <= len(cand_words) else (cand_words, words)
            )
            if shorter and shorter <= longer:
                return True

    handle = normalize_handle(candidate.handle)
    if handle and handle in index.handles:
        return True
    url_handle = extract_handle(candidate.url or "")
    if url_handle and url_handle in index.handles:
        return True

    canon = canonical_url(candidate.url)
    if canon and canon in index.urls:
        return True

    return False
