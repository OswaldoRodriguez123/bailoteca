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


def _parse_suffixed_number(number: str) -> float | None:
    """Parsea la parte numérica cuando hay sufijo K/M.

    Reglas:
    - un único comma seguido de 1–2 dígitos y sin punto → decimal (``4,9`` → 4.9);
    - commas agrupados en treses (``1,500`` / ``1,234,567``) → miles;
    - con punto y comma, manda la última posición (español ``1.234,5`` vs
      inglés ``1,234.5``);
    - cualquier otra cosa → None (no se adivina; la academia queda reintentable).
    """

    try:
        if "," in number and "." not in number:
            parts = number.split(",")
            if not all(part.isdigit() for part in parts):
                return None
            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                return float(f"{parts[0]}.{parts[1]}")
            if 1 <= len(parts[0]) <= 3 and all(len(part) == 3 for part in parts[1:]):
                return float("".join(parts))
            return None
        if "," in number and "." in number:
            if number.rfind(",") > number.rfind("."):
                return float(number.replace(".", "").replace(",", "."))
            return float(number.replace(",", ""))
        return float(number)
    except ValueError:
        return None


def parse_followers(text: str | None) -> int | None:
    """Extrae el número de seguidores de un texto libre.

    Con sufijo K/M la coma puede ser decimal o miles (ver
    ``_parse_suffixed_number``) y el punto se trata como decimal; sin
    sufijo se quitan ``.`` y ``,`` (``5.951`` → 5951). None si no hay match.
    """

    if not text:
        return None
    match = _FOLLOWERS_RE.search(text)
    if not match:
        return None
    number, suffix = match.group(1), match.group(2)
    if suffix:
        value = _parse_suffixed_number(number)
        if value is None:
            return None
        return int(value * _SUFFIX_MULTIPLIER[suffix.lower()])
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

    found: list[dict] = []
    for row in raw_rows:
        academy: dict = {}
        try:
            # Un savepoint por academia: si falla, solo se deshacen sus
            # escrituras y la transacción exterior sigue abierta para las demás.
            with conn.transaction():
                academy = _row_to_dict(row)
                source = search_factory(f'"{academy.get("name")}" seguidores instagram')
                candidates = (source.discover() or []) if source is not None else []
                for candidate in candidates:
                    followers = parse_followers(_description(candidate))
                    if followers is None:
                        continue
                    url = getattr(candidate, "url", None)
                    network = _network_from_url(url)
                    if apply:
                        # Escribir ANTES de registrar el hallazgo: si el update
                        # falla, no debe quedar una entrada fantasma de éxito.
                        conn.execute(
                            UPDATE_ACADEMY_SQL,
                            (followers, network, academy["id"]),
                        )
                    found.append(
                        {
                            "slug": academy.get("slug"),
                            "followers": followers,
                            "network": network,
                            "url": url,
                        }
                    )
                    break
        except Exception as exc:
            found.append({"slug": academy.get("slug"), "error": str(exc)})
    return found
