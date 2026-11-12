from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from bailoteca.models import Candidate
from bailoteca.normalize import candidate_key, normalize_name
from bailoteca.sources.base import Source
from bailoteca.sources.filters import filter_noise

# Hosts donde varias academias comparten dominio: la página no identifica al
# negocio, así que no se agrupan por sitio.
MULTI_TENANT_DOMAINS = frozenset(
    {
        "instagram.com",
        "facebook.com",
        "tiktok.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "google.com",
        "blogspot.com",
        "wordpress.com",
        "wixsite.com",
        "wix.com",
        "weebly.com",
        "squarespace.com",
        "jimdo.com",
        "webnode.com",
        "webnode.cl",
        "site123.me",
        "carrd.co",
        "notion.site",
        "github.io",
        "netlify.app",
        "vercel.app",
        "pages.dev",
        "webflow.io",
        "medium.com",
        "substack.com",
        "canva.site",
        "linktr.ee",
        "linkin.bio",
        "beacons.ai",
        "bio.link",
        "taplink.cc",
        "wa.me",
        "wa.link",
        "bit.ly",
        "eventbrite.cl",
        "eventbrite.com",
        "meetup.com",
        "jotform.com",
        "typeform.com",
        "calendly.com",
    }
)

# Sufijos de dos niveles: el dominio registrable son tres etiquetas.
MULTI_PART_SUFFIXES = frozenset(
    {
        "com.ar",
        "com.br",
        "com.mx",
        "com.co",
        "com.pe",
        "com.uy",
        "com.ec",
        "com.bo",
        "com.py",
        "com.ve",
        "com.do",
        "com.gt",
        "com.sv",
        "com.hn",
        "com.ni",
        "com.cr",
        "com.pa",
        "com.es",
        "com.au",
        "net.au",
        "co.uk",
        "org.uk",
        "co.nz",
        "co.za",
    }
)


@dataclass(frozen=True)
class CollectResult:
    candidates: list[Candidate]
    filtered_rules: int


def _loose_key(name: str, comuna: str | None) -> str:
    return f"{normalize_name(name)}|{normalize_name(comuna) if comuna else ''}"


def _loose_match_key(existing: Candidate, candidate: Candidate) -> bool:
    """Match by name; if both have comuna, require it to match."""
    if normalize_name(existing.name) != normalize_name(candidate.name):
        return False
    if existing.comuna and candidate.comuna:
        return normalize_name(existing.comuna) == normalize_name(candidate.comuna)
    return True


def _site_key(candidate: Candidate) -> str | None:
    """Dominio registrable del candidato, o None si no identifica al negocio."""
    url = (candidate.url or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    host = (urlsplit(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) < 2:
        return None
    if ".".join(labels[-2:]) in MULTI_PART_SUFFIXES:
        site = ".".join(labels[-3:])
    else:
        site = ".".join(labels[-2:])
    return None if site in MULTI_TENANT_DOMAINS else site


def _merge(existing: Candidate, candidate: Candidate) -> Candidate:
    return replace(
        existing,
        url=existing.url or candidate.url,
        handle=existing.handle or candidate.handle,
        comuna=existing.comuna or candidate.comuna,
        raw={**existing.raw, **candidate.raw},
    )


def collect(sources: list[Source]) -> CollectResult:
    discovered: list[Candidate] = []
    for source in sources:
        discovered.extend(source.discover())
    kept, dropped = filter_noise(discovered)

    merged: dict[str, Candidate] = {}
    by_site: dict[str, str] = {}
    for candidate in kept:
        key = candidate_key(
            candidate.name,
            candidate.url,
            candidate.handle,
            candidate.comuna,
        )
        site = _site_key(candidate)
        existing_key = key if key in merged else None
        if existing_key is None and site is not None:
            existing_key = by_site.get(site)
        if existing_key is None:
            # Try loose match by name (+ comuna if both have it) for cross-source dedupe
            for other_key, existing in merged.items():
                if _loose_match_key(existing, candidate):
                    existing_key = other_key
                    break

        if existing_key is not None:
            merged[existing_key] = _merge(merged[existing_key], candidate)
        else:
            existing_key = key
            merged[key] = candidate
        if site is not None:
            by_site[site] = existing_key
    return CollectResult(candidates=list(merged.values()), filtered_rules=dropped)
