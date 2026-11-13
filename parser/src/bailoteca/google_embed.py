"""Pins interpelado por Google Maps para direcciones sin ficha propia.

Fuente lateral (endpoint no oficial): ``maps.google.com/maps?q=...&output=embed``.
El blob ``initEmbed([...])`` que emite la página del mapa embebible es JSON
válido con la entidad resuelta: nombre/address, ``[lat, lng]``, y metadatos
(``gcid:*``, place id ``ChIJ…``). Este módulo solo lee; quién escribe y bajo
qué gate lo define ``geocode`` + el gate de acá.

Falla siempre suave: cualquier respuesta no parseable devuelve ``None``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

USER_AGENT = "Bailoteca/1.0 (+https://bailoteca.cl)"
EMBED_URL = "https://maps.google.com/maps"

_CHILE_LAT = (-57.0, -17.0)
_CHILE_LNG = (-76.0, -66.0)


@dataclass(frozen=True)
class EmbedResult:
    lat: float
    lng: float
    resolved_address: str
    place_id: str | None
    category: str | None  # p. ej. "dance_school", "subpremise"


_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?![A-Za-z0-9])")
_PLACE_ID_RE = re.compile(r"^ChIJ[A-Za-z0-9_-]+$")
_GCID_RE = re.compile(r"^gcid:([a-z_]+)$")


def house_number(address: str) -> str | None:
    """Primer token de dígitos de la dirección almacenada (sin tocar)."""
    m = _NUMBER_RE.search(address)
    return m.group(0) if m else None


def _walk(node: Any):
    """Itera todas las cadenas y listas del árbol decodificado."""
    if isinstance(node, list):
        yield node
        for item in node:
            yield from _walk(item)
    # los escalares se alcanzan como hijos de sus listas; nada que ceder aquí


def _walk_strings(node: Any):
    if isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)
    elif isinstance(node, str):
        yield node


def _entity_candidates(data: Any):
    for node in _walk(data):
        if (
            len(node) >= 3
            and isinstance(node[0], str)
            and node[0].startswith("0x")
            and isinstance(node[2], list)
            and len(node[2]) == 2
            and all(isinstance(v, (int, float)) for v in node[2])
        ):
            yield node


def _find_entity(data: Any) -> list | None:
    candidates = list(_entity_candidates(data))
    if not candidates:
        return None
    # Si hay varias entidades candidatas, preferir la que aporta una dirección con dígitos
    # (calle + número); fallback: la primera en orden de aparición.
    for node in candidates:
        resolved = node[1]
        if isinstance(resolved, str) and any(ch.isdigit() for ch in resolved):
            return node
    for node in candidates:
        if isinstance(node[1], str):
            return node
    return None


def parse_embed_html(html: str) -> EmbedResult | None:
    try:
        start = html.find("initEmbed(")
        if start == -1:
            return None
        payload_start = start + len("initEmbed(")
        end = html.find(");", payload_start)
        if end == -1:
            return None
        try:
            data = json.loads(html[payload_start:end].strip())
        except ValueError:
            # fallback greedy: `);` pudo aparecer dentro de un string JSON
            m = re.search(re.escape("initEmbed(") + r"(.*)\);", html, re.DOTALL)
            if m is None:
                return None
            data = json.loads(m.group(1).strip())
        entity = _find_entity(data)
        if entity is None:
            return None
        resolved = entity[1]
        if not isinstance(resolved, str):
            return None
        lat, lng = float(entity[2][0]), float(entity[2][1])
        place_id = None
        category = None
        for s in _walk_strings(data):
            if place_id is None and _PLACE_ID_RE.match(s):
                place_id = s
            if category is None:
                m = _GCID_RE.match(s)
                if m:
                    category = m.group(1)
            if place_id and category:
                break
        return EmbedResult(
            lat=lat, lng=lng, resolved_address=resolved,
            place_id=place_id, category=category,
        )
    except Exception:
        return None


def gate(address: str, resolved: EmbedResult) -> str | None:
    """None si el pin se acepta; si no, la razón del rechazo (es)."""
    number = house_number(address)
    if number is None:
        return "sin número en la dirección"
    if "Chile" not in resolved.resolved_address:
        return "resolución fuera de Chile"
    if not (_CHILE_LAT[0] <= resolved.lat <= _CHILE_LAT[1]):
        return "pin fuera de Chile continental"
    if not (_CHILE_LNG[0] <= resolved.lng <= _CHILE_LNG[1]):
        return "pin fuera de Chile continental"
    pattern = r"(?<!\d)0*" + str(int(number)) + r"(?!\d)"
    if re.search(pattern, resolved.resolved_address):
        return None
    return "número no coincide"


def resolve(
    address: str, comuna: str | None, client, timeout: float = 10.0
) -> EmbedResult | None:
    query = ", ".join(filter(None, [address, comuna, "Chile"]))
    try:
        resp = client.get(
            EMBED_URL,
            params={"q": query, "t": "m", "z": "14", "ie": "UTF8", "output": "embed"},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    body = getattr(resp, "text", None)
    if not isinstance(body, str):
        return None
    return parse_embed_html(body)
