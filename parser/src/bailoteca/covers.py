"""Portadas de academias alojadas en Supabase Storage."""

from __future__ import annotations

import httpx
from typing import Any
from urllib.parse import urlparse, urljoin

from bailoteca.db import connect, list_published
from bailoteca.enrich import MAX_BYTES, safe_url

IMAGES_MAX_AGE_DAYS = 180
BUCKET = "academy-covers"
MIN_IMAGE_BYTES = 500

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}
_COVER_SOURCES = {"instagram", "facebook", "web", "google", "manual"}


def _stream_get(url: str, *, timeout: float, headers: dict):
    """GET real con tope de lectura: se corta al superar MAX_BYTES."""
    from types import SimpleNamespace

    with httpx.stream(
        "GET",
        url,
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
    ) as response:
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_BYTES:
                break
        body = b"".join(chunks)[: MAX_BYTES + 1]
        encoding = getattr(response, "encoding", None) or "utf-8"
        return SimpleNamespace(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=body,
            text=body.decode(encoding, errors="replace"),
            url=str(response.url),
        )


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5


def _guarded_get(url, *, client: Any | None, timeout: float, headers: dict):
    """GET con safe_url por cada hop, sin seguir redirects automáticamente.

    Cada URL (original y cada Location) se valida con safe_url ANTES de
    pedirla; el cuerpo se corta al superar MAX_BYTES. Devuelve la respuesta
    o None si algún hop no es público, el cuerpo supera el tope o hay demasiados
    redirects.
    """
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        if not safe_url(current):
            return None
        try:
            if client is not None:
                response = client.get(
                    current,
                    timeout=timeout,
                    follow_redirects=False,
                    headers=headers,
                )
            else:
                response = _stream_get(current, timeout=timeout, headers=headers)
        except Exception:
            return None
        status = getattr(response, "status_code", 0)
        if status in _REDIRECT_STATUSES:
            response_headers = getattr(response, "headers", {}) or {}
            location = (
                response_headers.get("location")
                or response_headers.get("Location")
            )
            if not location:
                return None
            current = urljoin(current, location)
            continue
        # Defensa en profundidad: si el cliente expone la URL final (fakes o
        # transporte con redirects), se vuelve a validar.
        final = getattr(response, "url", None)
        if final is not None and not safe_url(str(final)):
            return None
        response_headers = getattr(response, "headers", {}) or {}
        raw_length = (
            response_headers.get("content-length")
            or response_headers.get("Content-Length")
        )
        try:
            declared = int(raw_length) if raw_length is not None else None
        except (TypeError, ValueError):
            declared = None
        if declared is not None and declared > MAX_BYTES:
            return None
        content = getattr(response, "content", b"") or b""
        if len(content) > MAX_BYTES:
            return None
        return response
    return None


def download_image(
    url: str,
    *,
    client: Any | None = None,
    timeout: float = 20.0,
) -> bytes | None:
    response = _guarded_get(url, client=client, timeout=timeout, headers=_HEADERS)
    if response is None:
        return None
    if getattr(response, "status_code", None) != 200:
        return None
    headers = getattr(response, "headers", {}) or {}
    content_type = (headers.get("content-type") or headers.get("Content-Type") or "").lower()
    if not content_type.startswith("image/"):
        return None
    content = getattr(response, "content", b"") or b""
    raw_length = headers.get("content-length") or headers.get("Content-Length")
    try:
        declared_length = int(raw_length) if raw_length is not None else len(content)
    except (TypeError, ValueError):
        declared_length = len(content)
    if declared_length < MIN_IMAGE_BYTES or len(content) < MIN_IMAGE_BYTES:
        return None
    return content


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _source_kind(url: str, declared: str | None = None) -> str:
    if declared in _COVER_SOURCES:
        return declared
    host = _host(url)
    if "instagram" in host or "scontent" in host:
        return "instagram"
    if "facebook" in host or "fbcdn" in host:
        return "facebook"
    if "google" in host:
        return "google"
    return "web"


def _is_instagram_logo(url: str) -> bool:
    return _host(url) == "static.cdninstagram.com"


def _resolve_source(
    academy: dict,
    recovered_sources: dict[str, str],
    *,
    client: Any | None = None,
) -> tuple[str, str] | None:
    slug = academy.get("slug") or ""
    recovered = recovered_sources.get(slug)
    if recovered:
        return recovered, _source_kind(recovered)

    google = academy.get("google") or {}
    thumbnail = (google or {}).get("thumbnail")
    if thumbnail and not _is_instagram_logo(thumbnail):
        return thumbnail, _source_kind(thumbnail, (google or {}).get("thumbnail_source"))

    from bailoteca.images import _LINK_ORDER, _fetch_og_image, _iter_link_urls

    ranked = sorted(
        _iter_link_urls(academy.get("links") or []),
        key=lambda pair: _LINK_ORDER.get(pair[0], 99),
    )
    for kind, url in ranked:
        image = _fetch_og_image(url, client=client)
        if image:
            return image, kind if kind in _COVER_SOURCES else "web"
    return None


def resolve_source_url(
    academy: dict,
    recovered_sources: dict[str, str],
    *,
    client: Any | None = None,
) -> str | None:
    resolved = _resolve_source(academy, recovered_sources, client=client)
    return resolved[0] if resolved else None


def _is_hosted(cover_url: str | None, supabase_url: str | None) -> bool:
    if not cover_url or not supabase_url:
        return False
    return cover_url.startswith(supabase_url.rstrip("/") + "/")


def backfill_covers(
    config,
    recovered_sources: dict[str, str],
    *,
    dry_run: bool = False,
    storage: Any | None = None,
    client: Any | None = None,
) -> dict:
    summary = {"hosted": [], "skipped": [], "missing": [], "failed": []}
    conn = connect(config.database_url)
    owns_storage = storage is None
    try:
        if not dry_run and storage is None:
            if not config.supabase_url or not config.supabase_service_role_key:
                raise RuntimeError(
                    "Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY para alojar portadas."
                )
            from bailoteca.supabase_storage import StorageClient

            storage = StorageClient(config.supabase_url, config.supabase_service_role_key)
        if not dry_run and storage is not None:
            storage.ensure_bucket(BUCKET)
        for academy in list_published(conn):
            slug = academy.get("slug") or ""
            if _is_hosted(academy.get("cover_url"), getattr(config, "supabase_url", None)):
                summary["skipped"].append(slug)
                continue
            source = _resolve_source(academy, recovered_sources, client=client)
            if source is None:
                summary["missing"].append(slug)
                continue
            source_url, source_kind = source
            image = download_image(source_url, client=client)
            if image is None:
                summary["failed"].append(slug)
                continue
            if not dry_run:
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
            summary["hosted"].append(slug)
        if not dry_run:
            conn.commit()
    finally:
        conn.close()
    return summary
