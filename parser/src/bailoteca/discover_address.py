"""Descubrimiento de direcciones de calle para sedes sólo con comuna.

Para las sedes de ``academy_locations`` sin ``address``, consulta (en orden):

1. Brave Search (plan free) con ``"<nombre>" <comuna> baile dirección`` — se
   prefieren resultados cuyo dominio sea propio de la academia.
2. Fetch de las páginas ``kind='web'`` propias de la academia (timeout, sólo
   texto plano) con el mismo regex de vía chilena.

Regla de oro: ``--apply`` escribe ``address`` **sólo** cuando la evidencia es
del dominio propio de la academia. Directorios, listados y blogs de terceros
se reportan como ``[revisar]`` y nunca se escriben; el usuario los revisa a mano.
Las coordenadas no las escribe este módulo: las asigna ``bailoteca geocode``.
Por defecto (dry-run) no escribe nada.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlsplit

USER_AGENT = "Bailoteca/1.0 (+https://bailoteca.cl)"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

LOCATIONS_SQL = """
select al.id::text as location_id,
       a.slug as academy_slug,
       a.name as academy_name,
       al.comuna,
       coalesce((select array_agg(l.url) from academy_links l
                  where l.academy_id = a.id and l.kind = 'web'), '{}') as own_urls
from academy_locations al
join academies a on a.id = al.academy_id
where al.address is null or btrim(al.address) = ''
order by a.slug, al.label
"""

UPDATE_ADDRESS_SQL = "update academy_locations set address = %s where id = %s"

_STREET_RE = re.compile(
    r"\b((?:Av\.?|Avenida|Calle|Camino|Pasaje|Psje\.?|Diagonal|Ruta)\s+"
    r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9'\.\-]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ0-9'\.\-]+){0,6}?"
    r"\s+\d{1,6})\b"
)
_SCRIPT_STYLE_RE = re.compile(r"<script.*?</script>|<style.*?</style>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_LOCATIONS_KEYS = ("location_id", "academy_slug", "academy_name", "comuna", "own_urls")


@dataclass(frozen=True)
class DiscoverProposal:
    location_id: str
    academy_slug: str
    comuna: str | None
    address: str | None
    source: str | None  # "brave" | "web" | None
    evidence: str | None
    own: bool
    reason: str | None  # None | "sin hallazgo"


def find_street(text: str | None) -> str | None:
    """Primera vía chilena con número en ``text``; normaliza espacios."""
    if not text:
        return None
    flat = _WS_RE.sub(" ", text)
    match = _STREET_RE.search(flat)
    return _WS_RE.sub(" ", match.group(1)).strip() if match else None


def _host(url: str) -> str | None:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else host or None


def _own_domains(own_urls: list[str]) -> list[str]:
    domains = []
    for url in own_urls or []:
        host = _host(url)
        if host and host not in domains:
            domains.append(host)
    return domains


def classify(evidence_url: str | None, evidence_text: str | None, own_urls: list[str]) -> bool:
    """True si la evidencia pertenece al dominio propio de la academia."""
    if not evidence_url:
        return False
    host = _host(evidence_url)
    if not host:
        return False
    for domain in _own_domains(own_urls):
        if host == domain or host.endswith("." + domain):
            return True
    return False


def _strip_html(raw: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", raw)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", unescape(text))


def _brave_results(client, api_key: str | None, name: str, comuna: str | None) -> list[dict]:
    if not api_key:
        return []
    query = " ".join(part for part in [f'"{name}"', comuna or "", "baile", "dirección"] if part)
    try:
        resp = client.get(
            BRAVE_URL,
            params={"q": query, "count": 5},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = (data or {}).get("web") or {}
        results = results.get("results") if isinstance(results, dict) else None
        return [item for item in results] if isinstance(results, list) else []
    except Exception:
        return []


def _clean(text: object) -> str:
    if not isinstance(text, str):
        return ""
    return _WS_RE.sub(" ", unescape(_TAG_RE.sub(" ", text))).strip()


def _fetch_web(client, url: str) -> str | None:
    try:
        resp = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    except Exception:
        return None
    if getattr(resp, "status_code", 0) < 200 or getattr(resp, "status_code", 0) >= 300:
        return None
    text = getattr(resp, "text", "")
    return _strip_html(text) if text else None


def _snippet(item: dict) -> str:
    parts = [_clean(item.get("title")), _clean(item.get("description"))]
    return " — ".join(part for part in parts if part)


def plan(conn) -> list[dict]:
    rows = conn.execute(LOCATIONS_SQL).fetchall()
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append(dict(row))
        else:
            out.append(dict(zip(_LOCATIONS_KEYS, row)))
    return out


def _propose(row: dict, client, api_key: str | None) -> DiscoverProposal:
    location_id = row["location_id"]
    slug = row.get("academy_slug") or ""
    comuna = row.get("comuna")
    own_urls = list(row.get("own_urls") or [])

    brave = _brave_results(client, api_key, row.get("academy_name") or slug, comuna)

    # 1) Brave propio
    for item in brave:
        snippet = _snippet(item)
        street = find_street(snippet)
        if street and classify(item.get("url"), snippet, own_urls):
            return DiscoverProposal(location_id, slug, comuna, street, "brave", snippet[:180], True, None)

    # 2) Web propia (siempre antes que terceros de Brave)
    for url in own_urls:
        text = _fetch_web(client, url)
        street = find_street(text)
        if street:
            evidence = text[:500] if text else None
            return DiscoverProposal(location_id, slug, comuna, street, "web", evidence, True, None)

    # 3) Brave de terceros (sólo listado; nunca se escribe con --apply)
    for item in brave:
        snippet = _snippet(item)
        street = find_street(snippet)
        if street:
            return DiscoverProposal(location_id, slug, comuna, street, "brave", snippet[:180], False, None)

    return DiscoverProposal(location_id, slug, comuna, None, None, None, False, "sin hallazgo")


def run(
    conn,
    client,
    brave_api_key: str | None,
    apply: bool = False,
    delay: float = 1.1,
    sleep=time.sleep,
) -> list[DiscoverProposal]:
    """Propone direcciones; con ``apply`` escribe sólo las de dominio propio."""
    proposals: list[DiscoverProposal] = []
    requests = 0
    for row in plan(conn):
        if requests:
            sleep(delay)
        requests += 1
        proposals.append(_propose(row, client, brave_api_key))

    if apply:
        for item in proposals:
            if item.own and item.address:
                conn.execute(UPDATE_ADDRESS_SQL, (item.address, item.location_id))
    return proposals
