"""Actualización mensual de portadas de academias.

Relee og:image desde los enlaces públicos (Instagram/Facebook/web) de cada
academia y vuelve a firmar/refrescar la URL guardada. Las fichas con
thumbnail proveniente de Google Maps (`thumbnail_source = 'google'`)
no se tocan porque actualizarlas es tarea de enrich-places.
"""

from __future__ import annotations

import httpx
import re

from datetime import datetime, timezone
from html import unescape
from typing import Protocol, Iterable

from psycopg.types.json import Jsonb

from bailoteca.db import connect, list_published

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml",
}
_LINK_ORDER = {"instagram": 0, "facebook": 1, "web": 2}


class HttpClient(Protocol):
    def get(self, url: str, **kwargs): ...


def _fetch_og_image(
    page_url: str,
    *,
    timeout: float = 15.0,
    client: HttpClient | None = None,
) -> str | None:
    http = client or httpx
    try:
        response = http.get(
            page_url,
            timeout=timeout,
            follow_redirects=True,
            headers=_HEADERS,
        )
    except Exception:
        return None
    if getattr(response, "status_code", 0) != 200:
        return None
    html = response.text
    match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if not match:
        match = re.search(r'content="([^"]+)" property="og:image"', html)
    if not match:
        return None
    og = unescape(match.group(1))
    try:
        img = http.get(
            og,
            timeout=timeout,
            follow_redirects=True,
            headers=_HEADERS,
        )
    except Exception:
        return None
    if getattr(img, "status_code", 0) != 200 or len(getattr(img, "content", b"")) < 500:
        return None
    return og


def _iter_link_urls(links: Iterable[dict]) -> Iterable[tuple[str, str]]:
    for link in links or []:
        kind = (link.get("kind") or "").lower()
        url = link.get("url") or ""
        if not url.startswith(("http://", "https://")):
            continue
        # evitamos rutas de login (Facebook/otras) que nunca tienen imagen útil
        if "login/" in url.lower() and "facebook.com" in url.lower():
            continue
        yield kind, url


def refresh_images(config, *, dry_run: bool = False, client: HttpClient | None = None) -> dict:
    summary = {"checked": 0, "updated": 0, "kept_google": 0, "no_image": 0}
    conn = connect(config.database_url)
    try:
        for academy in list_published(conn):
            summary["checked"] += 1
            google = academy.get("google") or {}
            # Fichas enriquecidas por Google Maps (via Places API) no se tocan:
            # su thumbnail viene de Google, no de redes sociales.
            if google.get("thumbnail_source") == "google" or google.get("place_id"):
                summary["kept_google"] += 1
                continue
            ranked = sorted(
                _iter_link_urls(academy.get("links") or []),
                key=lambda pair: _LINK_ORDER.get(pair[0], 99),
            )
            picked: str | None = None
            source_kind: str | None = None
            for kind, url in ranked:
                image = _fetch_og_image(url, client=client)
                if image:
                    picked, source_kind = image, kind
                    break
            if picked is None:
                summary["no_image"] += 1
                continue
            new_google = dict(google)
            new_google.update(
                {
                    "thumbnail": picked,
                    "thumbnail_source": source_kind,
                    "thumbnail_fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if not dry_run:
                conn.execute(
                    "update academies set google = %s, updated_at = now() where id = %s",
                    (Jsonb(new_google), academy["id"]),
                )
            summary["updated"] += 1
        conn.commit()
    finally:
        conn.close()
    return summary
