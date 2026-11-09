"""Descarga y extracción de datos de una academia, con caché y URLs seguras."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from bailoteca.models import Candidate

MAX_DESCRIPTION = 300
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 10.0
INSTAGRAM_POST_PREFIXES = ("/p/", "/reel/", "/tv/", "/stories/")
SHARE_PATHS = ("/sharer", "/share")


@dataclass(frozen=True)
class Page:
    url: str
    status: int
    html: str
    text: str


class Fetcher(Protocol):
    def get(self, url: str) -> Page: ...


@dataclass(frozen=True)
class Enriched:
    candidate: Candidate
    page_url: str | None
    text: str
    address: str | None
    comuna: str | None
    links: dict[str, list[str]] = field(default_factory=dict)
    description: str | None = None
    evidence: dict = field(default_factory=dict)


import functools
import ipaddress
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# Cache DNS resolution results to avoid repeated lookups and slowdowns
_DNS_CACHE: dict[str, tuple[list[str], float]] = {}
_DNS_CACHE_TTL = 300  # 5 minutes


def _resolve_host(host: str) -> list[str]:
    """Resolve hostname to IP addresses, with caching."""
    now = time.monotonic()
    if host in _DNS_CACHE:
        ips, cached_at = _DNS_CACHE[host]
        if now - cached_at < _DNS_CACHE_TTL:
            return ips
    try:
        # Use getaddrinfo with a short timeout
        socket.setdefaulttimeout(2.0)
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
        ips = [info[4][0] for info in infos]
    except Exception:
        ips = []
    finally:
        socket.setdefaulttimeout(None)
    _DNS_CACHE[host] = (ips, now)
    return ips


def safe_url(url: str) -> bool:
    if not url:
        return False
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"}:
        return False
    host = parts.hostname
    if not host:
        return False
    host = host.lower()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Hostname: resolve and check all IPs
        ips = _resolve_host(host)
        if not ips:
            # Could not resolve; be conservative and reject
            return False
        for ip_str in ips:
            try:
                ip = ipaddress.ip_address(ip_str)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_unspecified
                    or ip.is_multicast
                ):
                    return False
            except ValueError:
                continue
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        or address.is_multicast
    )


def extract_jsonld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            blocks.append(data)
        elif isinstance(data, list):
            blocks.extend(item for item in data if isinstance(item, dict))
    return blocks


def _find_address(value: object) -> tuple[str | None, str | None]:
    if isinstance(value, dict):
        if value.get("streetAddress"):
            return value.get("streetAddress"), value.get("addressLocality")
        for nested in value.values():
            found = _find_address(nested)
            if found != (None, None):
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_address(nested)
            if found != (None, None):
                return found
    return None, None


def extract_address(jsonlds: list[dict]) -> tuple[str | None, str | None]:
    for block in jsonlds:
        address, comuna = _find_address(block)
        if address:
            return address, comuna
    return None, None


def _normalize_social(kind: str, raw: str) -> str | None:
    if kind == "email":
        return raw if raw.startswith("mailto:") else f"mailto:{raw}"
    if kind == "phone":
        return raw if raw.startswith("tel:") else f"tel:{raw}"
    if raw.startswith("mailto:") or raw.startswith("tel:"):
        return raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or ""
    if kind == "instagram":
        if host != "instagram.com" or path.startswith(INSTAGRAM_POST_PREFIXES):
            return None
        handle = path.strip("/").split("/")[0]
        return f"https://instagram.com/{handle}" if handle else None
    if any(marker in path for marker in SHARE_PATHS):
        return None
    return raw


def _add_link(links: dict[str, list[str]], kind: str, url: str | None) -> None:
    if not url:
        return
    bucket = links.setdefault(kind, [])
    if url not in bucket:
        bucket.append(url)


def _classify_href(href: str) -> tuple[str, str] | None:
    if not href:
        return None
    if href.startswith("mailto:"):
        return "email", href
    if href.startswith("tel:"):
        return "phone", href
    parts = urlsplit(href)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "instagram.com":
        return "instagram", href
    if host in {"facebook.com", "fb.com"}:
        return "facebook", href
    if host == "tiktok.com":
        return "tiktok", href
    if host in {"wa.me", "whatsapp.com"}:
        return "whatsapp", href
    return None


def extract_social_links(html: str, base_url: str) -> dict[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, list[str]] = {}
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor["href"].strip())
        classified = _classify_href(href)
        if not classified:
            continue
        kind, candidate_url = classified
        normalized = _normalize_social(kind, candidate_url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            _add_link(links, kind, normalized)
    for block in extract_jsonld(html):
        same_as = block.get("sameAs")
        if isinstance(same_as, str):
            same_as = [same_as]
        if not isinstance(same_as, list):
            continue
        for entry in same_as:
            if not isinstance(entry, str):
                continue
            classified = _classify_href(entry)
            if not classified:
                continue
            kind, candidate_url = classified
            normalized = _normalize_social(kind, candidate_url)
            if normalized and normalized not in seen:
                seen.add(normalized)
                _add_link(links, kind, normalized)
    return links


def extract_description(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ('meta[name="description"]', 'meta[property="og:description"]'):
        tag = soup.select_one(selector)
        if tag and tag.get("content"):
            text = " ".join(tag["content"].split())
            if text:
                return _truncate(text)
    return None


def _truncate(text: str) -> str:
    if len(text) <= MAX_DESCRIPTION:
        return text
    cut = text[:MAX_DESCRIPTION]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut


def _text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def _is_instagram_profile(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host == "instagram.com" and parts.path and not parts.path.startswith(
        ("/p/", "/reel/", "/tv/", "/stories/")
    )


def enrich(candidate: Candidate, fetcher: Fetcher) -> Enriched:
    links: dict[str, list[str]] = {}
    if candidate.handle:
        _add_link(links, "instagram", f"https://instagram.com/{candidate.handle}")

    page_url = candidate.url
    text = ""
    address = None
    comuna = candidate.comuna
    description = None
    evidence: dict = {"name": {"source_url": candidate.url, "method": candidate.source}}

    if candidate.url and safe_url(candidate.url) and not _is_instagram_profile(
        candidate.url
    ):
        page = fetcher.get(candidate.url)
        page_url = page.url or page_url
        text = page.text or _text_from_html(page.html)
        if page.status == 200 and page.html:
            jsonlds = extract_jsonld(page.html)
            address, jsonld_comuna = extract_address(jsonlds)
            comuna = comuna or jsonld_comuna
            description = extract_description(page.html)
            for kind, urls in extract_social_links(page.html, page_url).items():
                for url in urls:
                    _add_link(links, kind, url)
            if description:
                evidence["description"] = {
                    "source_url": page_url,
                    "method": "meta",
                }
            if address:
                evidence["address"] = {
                    "source_url": page_url,
                    "method": "jsonld",
                }
            if comuna:
                evidence["comuna"] = {
                    "source_url": page_url,
                    "method": "jsonld",
                }
            if links:
                evidence["links"] = {
                    "source_url": page_url,
                    "method": "anchors+jsonld",
                }

    return Enriched(
        candidate=candidate,
        page_url=page_url,
        text=text,
        address=address,
        comuna=comuna,
        links=links,
        description=description,
        evidence=evidence,
    )


class CachedFetcher:
    def __init__(self, fetcher: Fetcher, cache_dir: Path):
        self.fetcher = fetcher
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.html", self.cache_dir / f"{key}.json"

    def get(self, url: str) -> Page:
        html_path, meta_path = self._paths(url)
        if html_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return Page(
                url=meta["url"],
                status=meta["status"],
                html=html_path.read_text(encoding="utf-8"),
                text=meta.get("text", ""),
            )
        page = self.fetcher.get(url)
        if page.status < 400:
            html_path.write_text(page.html, encoding="utf-8")
            meta_path.write_text(
                json.dumps(
                    {"url": page.url, "status": page.status, "text": page.text},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        return page


class HttpxFetcher:
    """Descarga real con límite de tamaño, timeout y una petición por segundo y host."""

    def __init__(
        self,
        timeout: float = TIMEOUT_SECONDS,
        min_interval: float = 1.0,
        stream_fn=None,
    ):
        self.timeout = timeout
        self.min_interval = min_interval
        self._last_request: dict[str, float] = {}
        self._stream_fn = stream_fn or (lambda *a, **k: __import__("httpx").stream(*a, **k))

    def get(self, url: str) -> Page:
        import httpx

        host = urlsplit(url).hostname or ""
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request[host] = time.monotonic()

        try:
            with self._stream_fn(
                "GET",
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "directorio-baile/0.1"},
            ) as response:
                final_url = str(response.url)
                if not safe_url(final_url):
                    return Page(url=final_url, status=0, html="", text="")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    if total + len(chunk) > MAX_BYTES:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                body = b"".join(chunks)
                html = body.decode(response.encoding or "utf-8", errors="replace")
                return Page(
                    url=final_url,
                    status=response.status_code,
                    html=html,
                    text=_text_from_html(html),
                )
        except httpx.HTTPError:
            return Page(url=url, status=0, html="", text="")
