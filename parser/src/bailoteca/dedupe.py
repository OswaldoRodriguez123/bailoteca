"""Descarte de candidatos ya conocidos: publicados o en propuestas pendientes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.normalize import normalize_handle, normalize_name

_SOCIAL_HOSTS = {"instagram.com", "facebook.com"}
# Hosts de mensajería/redes compartidas: no identifican un negocio por sí solos.
_MESSAGING_HOSTS = {"wa.me", "whatsapp.com"}
# Hosts de video/social de distribución masiva: sus "raíces" no son un negocio.
_SHARED_HOSTS = _SOCIAL_HOSTS | _MESSAGING_HOSTS | {
    "tiktok.com",
    "x.com",
    "twitter.com",
    "youtube.com",
}
# Primer segmento de URL que es navegación de la plataforma, no un handle.
_GENERIC_HANDLES = frozenset({
    "profile.php", "share.php", "sharer", "sharer.php",
    "people", "p", "reel", "reels", "events",
    "photo", "photos", "videos", "groups", "watch",
    "hashtag", "explore", "stories", "pages",
})
# Hosts compartidos por directorios/agregadores: no identifican un negocio distinto.
AGGREGATOR_HOSTS = frozenset({
    "agendapro.cl",
    "mercantil.com",
    "evisos.cl",
    "varios.cl",
})


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


def root_host(url: str) -> str | None:
    parsed = url_parts(url or "")
    if parsed is None:
        return None
    host, _ = parsed
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    return ".".join(labels[-2:])


def canonical_url(url: str | None) -> str | None:
    parsed = url_parts(url or "")
    if parsed is None:
        return None
    host, path = parsed
    clean_path = path.rstrip("/") or "/"
    query = ""
    # En hosts sociales el `?id=` es la identidad del perfil; el resto de la
    # query (tracking, locale) se ignora.
    if host in _SOCIAL_HOSTS:
        try:
            parts = urlsplit((url or "").strip())
        except ValueError:
            parts = None
        if parts:
            for pair in parts.query.split("&"):
                key, _, value = pair.partition("=")
                if key == "id" and value.isdigit():
                    query = f"?id={value}"
                    break
        # Rutas de navegación/compartición sin handle ni ?id= no son una
        # identidad estable: dos negocios distintos compartirían el mismo URL.
        first_segment = next((seg for seg in (path or "/").split("/") if seg), "")
        if first_segment.lower() in _GENERIC_HANDLES and not query:
            return None
    return f"https://{host}{clean_path.lower()}{query}"


def _phone_key(url: str | None) -> str | None:
    """Extrae el teléfono canónico de un URL, o None.

    Solo tel: (el path) y wa.me/whatsapp.com (el primer segmento, y solo si
    son dígitos). Ignora query, fragmento y codificación de porcentaje: los
    dígitos dentro de esas partes no son teléfonos, y los IDs de
    facebook.com/profile.php no son teléfono real porque ese host no es
    wa.me ni lleva prefijo tel:.
    """
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme == "tel":
        digits = re.sub(r"\D", "", parts.path or "")
    else:
        host = (parts.hostname or "").lower().removeprefix("www.")
        if host not in ("wa.me", "whatsapp.com"):
            return None
        segments = [seg for seg in (parts.path or "").split("/") if seg]
        if not segments or not segments[0].isdigit():
            return None
        digits = segments[0]
    if len(digits) < 8:
        return None
    return digits[-9:] if len(digits) > 9 else digits


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
    if not handle or handle in _GENERIC_HANDLES:
        return None
    return handle


@dataclass(frozen=True)
class ExistingIndex:
    names: tuple[frozenset[str], ...] = field(default_factory=tuple)
    urls: frozenset[str] = frozenset()
    handles: frozenset[str] = frozenset()
    phones: frozenset[str] = frozenset()
    roots: frozenset[str] = frozenset()


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
    phones: set[str] = set()
    roots: set[str] = set()
    for entry in list(published) + list(pending):
        words = _words(entry.get("name"))
        if words:
            names.append(words)
        for link in _iter_links(entry):
            url = link.get("url") or ""
            key = _phone_key(url)
            if key:
                phones.add(key)
            host = url_parts(url)
            if host is None:
                continue
            handle = extract_handle(url)
            if handle:
                handles.add(handle)
            canon = canonical_url(url)
            if canon:
                urls.add(canon)
            root = root_host(url)
            if root and root not in _SHARED_HOSTS and root not in AGGREGATOR_HOSTS:
                roots.add(root)
    return ExistingIndex(
        names=tuple(names),
        urls=frozenset(urls),
        handles=frozenset(handles),
        phones=frozenset(phones),
        roots=frozenset(roots),
    )


def is_duplicate(
    candidate: Candidate,
    index: ExistingIndex,
    extra_links: list[dict] | None = None,
) -> bool:
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

    link_urls = [candidate.url or ""]
    for link in extra_links or []:
        link_urls.append(link.get("url") or "")

    handle = normalize_handle(candidate.handle)
    if handle and handle in index.handles:
        return True

    for link_url in link_urls:
        url_handle = extract_handle(link_url)
        if url_handle and url_handle in index.handles:
            return True

        canon = canonical_url(link_url)
        if canon and canon in index.urls:
            return True

        root = root_host(link_url)
        if (
            root
            and root not in _SHARED_HOSTS
            and root not in AGGREGATOR_HOSTS
            and root in index.roots
        ):
            return True

        key = _phone_key(link_url)
        if key and key in index.phones:
            return True

    return False
