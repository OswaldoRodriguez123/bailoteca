"""Actualización semestral de portadas de academias.

Relee og:image desde los enlaces públicos (Instagram/Facebook/web) de cada
academia y aloja la imagen resultante en Supabase Storage. Las fichas con
portada reciente (< 180 días) o vinculadas a Google Maps no se tocan.
"""

from __future__ import annotations

import re

from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Protocol, Iterable
from urllib.parse import urlparse

from bailoteca.covers import (
    BUCKET,
    IMAGES_MAX_AGE_DAYS,
    _guarded_get,
    _resolve_source,
    download_image,
)
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
    page = _guarded_get(page_url, client=client, timeout=timeout, headers=_HEADERS)
    if page is None:
        return None
    if getattr(page, "status_code", 0) != 200:
        return None
    html = page.text
    match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if not match:
        match = re.search(r'content="([^"]+)" property="og:image"', html)
    if not match:
        return None
    og = unescape(match.group(1))
    # Instagram sirve su logo de UI (static.cdninstagram.com/rsrc.php/...) como
    # og:image cuando el scraper anónimo es bloqueado; no es contenido de la academia.
    if (urlparse(og).hostname or "").lower() == "static.cdninstagram.com":
        return None
    img = _guarded_get(og, client=client, timeout=timeout, headers=_HEADERS)
    if img is None:
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


def _parse_fetched_at(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_fresh(academy: dict, *, now: datetime | None = None) -> bool:
    fetched_at = _parse_fetched_at(academy.get("cover_fetched_at"))
    if fetched_at is None:
        return False
    reference = now or datetime.now(timezone.utc)
    return reference - fetched_at < timedelta(days=IMAGES_MAX_AGE_DAYS)


def _ensure_storage(config, storage):
    if storage is not None:
        return storage
    if not config.supabase_url or not config.supabase_service_role_key:
        raise RuntimeError(
            "Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY para alojar portadas."
        )
    from bailoteca.supabase_storage import StorageClient

    return StorageClient(config.supabase_url, config.supabase_service_role_key)


def refresh_images(
    config,
    *,
    dry_run: bool = False,
    client: HttpClient | None = None,
    storage=None,
) -> dict:
    summary = {
        "checked": 0,
        "updated": 0,
        "kept_google": 0,
        "fresh": 0,
        "no_image": 0,
    }
    conn = connect(config.database_url)
    storage_ready = False
    try:
        for academy in list_published(conn):
            summary["checked"] += 1
            if _is_fresh(academy):
                summary["fresh"] += 1
                continue
            google = academy.get("google") or {}
            # Fichas enriquecidas por Google Maps (via Places API) no se tocan:
            # su portada la gestiona enrich-places.
            if google.get("thumbnail_source") == "google" or google.get("place_id"):
                summary["kept_google"] += 1
                continue
            source = _resolve_source(academy, {}, client=client)
            if source is None:
                summary["no_image"] += 1
                continue
            source_url, source_kind = source
            image = download_image(source_url, client=client)
            if image is None:
                summary["no_image"] += 1
                continue
            if not dry_run:
                if storage is None:
                    storage = _ensure_storage(config, storage)
                if not storage_ready:
                    storage.ensure_bucket(BUCKET)
                    storage_ready = True
                slug = academy["slug"]
                key = f"{slug}.jpg"
                storage.upload(BUCKET, key, image, "image/jpeg")
                cover_url = storage.public_url(BUCKET, key)
                conn.execute(
                    """
                    update academies
                    set cover_url = %s,
                        cover_source = %s,
                        cover_fetched_at = now(),
                        updated_at = now()
                    where id = %s
                    """,
                    (cover_url, source_kind, academy["id"]),
                )
            summary["updated"] += 1
        conn.commit()
    finally:
        conn.close()
    return summary
