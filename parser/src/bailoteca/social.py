"""Backfill de seguidores sociales para academias publicadas.

Hace una búsqueda por academia (``f'"{name}" seguidores instagram'``) con los
providers de búsqueda configurados, toma el primer candidato cuya descripción
incluye un número de seguidores y, con ``--apply``, escribe
``social_followers``/``social_network`` en la academia. Por defecto (dry-run)
solo devuelve el plan; no escribe.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

ACADEMIES_QUERY = """
select id::text, slug, name
from academies
where social_followers is null
order by name asc
"""

UPDATE_ACADEMY_SQL = """
update academies
set social_followers = %s, social_network = %s, updated_at = now()
where id = %s
"""

_FOLLOWERS_RE = re.compile(r"(\d[\d.,]*)\s*([KkMm])?\s*(?:followers|seguidores)", re.I)
_SUFFIX_MULTIPLIER = {"k": 1_000, "m": 1_000_000}


def parse_followers(text: str | None) -> int | None:
    """Extrae el número de seguidores de un texto libre.

    Con sufijo K/M el punto se trata como decimal (``1.5M`` → 1.500.000);
    sin sufijo se quitan ``.`` y ``,`` (``5.951`` → 5951). None si no hay match.
    """

    if not text:
        return None
    match = _FOLLOWERS_RE.search(text)
    if not match:
        return None
    number, suffix = match.group(1), match.group(2)
    if suffix:
        try:
            return int(float(number.replace(",", "")) * _SUFFIX_MULTIPLIER[suffix.lower()])
        except ValueError:
            return None
    digits = re.sub(r"[.,]", "", number)
    try:
        return int(digits)
    except ValueError:
        return None


_NETWORK_HOSTS = (
    ("instagram", "instagram"),
    ("facebook", "facebook"),
    ("fb.com", "facebook"),
    ("tiktok", "tiktok"),
)


def _network_from_url(url: str | None) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    for needle, network in _NETWORK_HOSTS:
        if needle in host:
            return network
    return "web"


def _row_to_dict(row) -> dict:
    if isinstance(row, dict):
        return dict(row)
    keys = ("id", "slug", "name")
    return dict(zip(keys, row))


def _description(candidate) -> str:
    raw = getattr(candidate, "raw", None) or {}
    description = raw.get("description") if isinstance(raw, dict) else None
    if not isinstance(description, str):
        description = str(description or "")
    return description


def run(conn, search_factory, apply: bool = False) -> list[dict]:
    """Busca seguidores para academias con social_followers null.

    Una búsqueda por academia; gana el primer candidato cuya descripción rinde
    un número. Con ``apply`` ejecuta el update; si no, solo reporta. Devuelve
    la lista de hallazgos ``{"slug", "followers", "network", "url"}``.
    """

    raw_rows = conn.execute(ACADEMIES_QUERY).fetchall()
    academies = [_row_to_dict(row) for row in raw_rows]

    found: list[dict] = []
    for academy in academies:
        source = search_factory(f'"{academy.get("name")}" seguidores instagram')
        candidates = (source.discover() or []) if source is not None else []
        for candidate in candidates:
            followers = parse_followers(_description(candidate))
            if followers is None:
                continue
            url = getattr(candidate, "url", None)
            network = _network_from_url(url)
            found.append(
                {
                    "slug": academy.get("slug"),
                    "followers": followers,
                    "network": network,
                    "url": url,
                }
            )
            if apply:
                conn.execute(
                    UPDATE_ACADEMY_SQL,
                    (followers, network, academy["id"]),
                )
            break
    return found
