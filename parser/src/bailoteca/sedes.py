"""Backfill asistido de sedes para academias publicadas sin sede.

Pasada A: extrae comuna + dirección desde nombre, descripción y (solo si
``looks_chilean``) la dirección de Google Maps. ``source_url`` = primer
``source_urls`` de la academia; si está vacío, fallback al link de la propia
academia (prioridad web > facebook > instagram > tiktok > youtube > other;
excluye email/phone/whatsapp y URLs mailto:/tel:/https://wa.me/). Sin nada
usable, la sede queda SIN FUENTE y con --apply no se inserta.

Antes de Gemini corre un pre-paso determinista (``comuna_from_text``) sobre la
descripción; salta si ``google.address`` existe y no parezca chilena (ni el
pre-paso ni Gemini asignan sede en ese caso). El pre-paso marca ``via='texto'``
(solo trazabilidad, no se persiste); ``source_url`` sale del fallback de links. Pasada B: busca en Brave
(``f'"{name}" Santiago comuna'``, una query, num=3) y extrae por candidato.
Compuerta (``extract_rm_comuna``): match normalizado EXACTO contra las comunas
RM del catálogo oficial; cualquier otra cosa → None (sin sede). Con ``--apply``
inserta en ``academy_locations`` (label='Sede', lat/lng null, region derivada
del catálogo); por defecto solo imprime el plan (dry-run).
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from bailoteca.llm import DEFAULT_MODELS, RETRYABLE_STATUS
from bailoteca_shared.regions import (
    comunas_in_region,
    normalize_comuna,
    region_slug_for_comuna,
)

RM_COMUNAS = comunas_in_region("metropolitana")
_RM_LOOKUP = {normalize_comuna(c): c for c in RM_COMUNAS}

_RM_LIST = ", ".join(RM_COMUNAS)

ACADEMIES_QUERY = """
select a.id::text, a.slug, a.name, a.description, a.source_urls, a.google,
       coalesce((select json_agg(json_build_object('kind', l.kind, 'url', l.url) order by l.kind)
                 from academy_links l where l.academy_id = a.id), '[]') as links
from academies a
where a.status <> 'closed' and not exists (select 1 from academy_locations al where al.academy_id=a.id)
order by a.slug
"""

INSERT_LOCATION_SQL = """
insert into academy_locations (academy_id, label, address, comuna, lat, lng, region, source_url)
values (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
"""

PROMPT_SEDE = """Eres un asistente que identifica la sede de una academia de baile en Santiago de Chile.

Datos de la academia:
---
Nombre: {name}
Descripción: {description}
{evidence}---

Comunas oficiales de la Región Metropolitana (elige UNA, exactamente como aparece en esta lista):
{rm_list}

Devuelve SOLO un objeto JSON con esta forma:
{{"comuna": "<una de la lista>", "address": "..."}}

O el literal JSON null si no tienes evidencia suficiente.

Reglas:
- "comuna" debe ser exactamente una de las comunas de la lista (mismo nombre oficial).
- "address" debe ser la dirección completa tal como aparece en los datos.
- Nunca inventes una comuna ni una dirección. Ante la duda, responde null.
"""


class SedeLLM(Protocol):
    def extract(self, prompt: str) -> dict | None: ...


class HttpPost(Protocol):
    def post(self, url: str, headers: dict, json: dict): ...


def looks_chilean(text: str | None) -> bool:
    return bool(
        re.search(
            r"(?i)chile|santiago|región metropolitana|region metropolitana",
            text or "",
        )
    )


def _google_address(academy: dict) -> str | None:
    google = academy.get("google")
    if not isinstance(google, dict):
        return None
    address = google.get("address")
    return address if isinstance(address, str) else None


def build_pass_a_prompt(academy: dict) -> str:
    evidence_lines: list[str] = []
    google_address = _google_address(academy)
    if google_address and looks_chilean(google_address):
        evidence_lines.append(f"Dirección (Google Maps): {google_address}\n")
    return PROMPT_SEDE.format(
        name=academy.get("name") or "",
        description=academy.get("description") or "",
        evidence="".join(evidence_lines),
        rm_list=_RM_LIST,
    )


def build_pass_b_prompt(academy: dict, snippet: str) -> str:
    return PROMPT_SEDE.format(
        name=academy.get("name") or "",
        description=academy.get("description") or "",
        evidence=f"Resultado de búsqueda:\n{snippet}\n",
        rm_list=_RM_LIST,
    )


def parse_llm_json(text: str | None) -> dict | None:
    """json.loads tolerante a fences ```json ... ``` y a texto con llaves alrededor."""

    if not text:
        return None
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(?P<body>.*?)\s*```$", cleaned, re.S | re.I)
    if fence:
        cleaned = fence.group("body").strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def comuna_from_text(text: str) -> str | None:
    """Pre-paso determinista: comuna RM desde el texto.

    Busca comunas RM (catálogo oficial) en el texto normalizado con límites de
    palabra: cualquier carácter no alfanumérico colapsa a espacio y el texto
    queda padded con espacios. Devuelve el match con
    menor posición, EXCEPTO: si el primero es ``Santiago`` y existe otro match
    posterior distinto de Santiago, devuelve ese otro (p. ej. "Radal 189,
    Estación Central, Santiago" → "Estación Central"). Si hay 2+ comunas RM
    distintas no-Santiago en el texto → None (ambiguo). Siempre devuelve el
    nombre oficial del catálogo, nunca el texto crudo.
    """

    padded = _word_pad(text or "")
    matches: list[tuple[int, str]] = []
    for comuna in RM_COMUNAS:
        token = _word_pad(comuna)
        start = 0
        while True:
            index = padded.find(token, start)
            if index == -1:
                break
            matches.append((index, comuna))
            start = index + 1
    if not matches:
        return None
    matches.sort(key=lambda match: match[0])
    distinct_non_santiago = {name for _, name in matches if name != "Santiago"}
    if len(distinct_non_santiago) >= 2:
        return None
    first = matches[0][1]
    if first == "Santiago":
        for _, name in matches:
            if name != "Santiago":
                return name
    return first


def _word_pad(text: str) -> str:
    """normalize_comuna + cualquier no-alfanumérico como separador + pad con espacios."""

    words = re.sub(r"[^a-z0-9 ]+", " ", normalize_comuna(text)).split()
    return f" {' '.join(words)} "


def _has_foreign_google_address(academy: dict) -> bool:
    """True si hay google.address y NO parece chilena (sala-marina: España)."""

    address = _google_address(academy)
    return bool(address) and not looks_chilean(address)


def _sede_from_text(academy: dict) -> dict | None:
    """Sede desde el pre-paso determinista sobre la descripción (sin LLM).

    address = primera oración de la descripción que contiene la comuna
    (split en . ! ? \\n; trim; truncada a 200 chars; None si no hay).
    source_url = fallback de links de la academia (web > facebook > instagram >
    tiktok > youtube > other). via='texto' es solo para trazabilidad interna.
    """

    description = academy.get("description") or ""
    comuna = comuna_from_text(description)
    if comuna is None:
        return None
    needle = _word_pad(comuna)
    address = None
    for piece in re.split(r"[.!?\n]", description):
        sentence = " ".join(piece.split())
        if not sentence:
            continue
        if needle in _word_pad(sentence):
            address = sentence[:200]
            break
    return {
        "address": address,
        "comuna": comuna,
        "source_url": _fallback_link(academy.get("links")),
        "via": "texto",
    }


def extract_rm_comuna(comuna_raw: str | None) -> str | None:
    """Normaliza vía catálogo; debe ser una comuna RM exacta (nombre oficial).

    Match exacto tras normalización (NFD, ignora mayúsculas y acentos).
    Sin abreviaciones ni fuzziness: cualquier otra cosa → None.
    """

    if not isinstance(comuna_raw, str) or not comuna_raw.strip():
        return None
    return _RM_LOOKUP.get(normalize_comuna(comuna_raw))


def pass_a(academy: dict, llm) -> dict | None:
    return _pass_a(academy, llm)[0]


def _pass_a(academy: dict, llm) -> tuple[dict | None, bool]:
    """Devuelve (sede, ambigua). ambigua = el LLM respondió pero no pasó el gate."""

    data = llm.extract(build_pass_a_prompt(academy))
    if data is None:
        return None, False
    comuna = extract_rm_comuna(data.get("comuna"))
    address = data.get("address")
    if comuna is None or not isinstance(address, str) or not address.strip():
        return None, True
    source_urls = academy.get("source_urls") or []
    # Fallback: si la academia no declara source_urls, usar su propio link
    # (web > facebook > instagram > tiktok > youtube > other) como evidencia.
    source_url = source_urls[0] if source_urls else _fallback_link(academy.get("links"))
    return (
        {
            "address": " ".join(address.split()),
            "comuna": comuna,
            "source_url": source_url,
        },
        False,
    )


def pass_b(academy: dict, brave, llm) -> dict | None:
    return _pass_b(academy, brave, llm)[0]


def _pass_b(academy: dict, brave, llm) -> tuple[dict | None, bool]:
    """Recorre candidatos Brave en orden; gana el primero cuyo snippet pase el gate."""

    if brave is None or llm is None:
        return None, False
    candidates = (brave.discover() or [])[:3]
    ambiguous = False
    for candidate in candidates:
        description = (candidate.raw or {}).get("description") or ""
        if not isinstance(description, str):
            description = str(description)
        name = (candidate.name or "").strip()
        if description.strip():
            snippet = f"{name}: {description}" if name else description
        elif name:
            snippet = name
        else:
            continue
        data = llm.extract(build_pass_b_prompt(academy, snippet))
        if data is None:
            continue
        comuna = extract_rm_comuna(data.get("comuna"))
        address = data.get("address")
        if comuna is None or not isinstance(address, str) or not address.strip():
            ambiguous = True
            continue
        return (
            {
                "address": " ".join(address.split()),
                "comuna": comuna,
                "source_url": candidate.url,
            },
            False,
        )
    return None, ambiguous


_KIND_RANK = {"web": 0, "facebook": 1, "instagram": 2, "tiktok": 3, "youtube": 4, "other": 5}
_EXCLUDED_KINDS = {"email", "phone", "whatsapp"}
_EXCLUDED_URL_PREFIXES = ("mailto:", "tel:", "https://wa.me/")


def _fallback_link(links) -> str | None:
    """Primer link usable por prioridad web > facebook > instagram > tiktok > youtube > other.

    Excluye kinds email/phone/whatsapp y URLs mailto:/tel:/https://wa.me/.
    Kinds desconocidos cuentan como 'other'. None si no hay nada usable.
    """

    if isinstance(links, str):
        try:
            links = json.loads(links)
        except Exception:
            return None
    if not isinstance(links, list):
        return None
    usable: list[tuple[int, int, str]] = []
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            continue
        kind = str(link.get("kind") or "").strip().lower()
        url = link.get("url")
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url:
            continue
        if kind in _EXCLUDED_KINDS:
            continue
        if url.lower().startswith(_EXCLUDED_URL_PREFIXES):
            continue
        usable.append((_KIND_RANK.get(kind, _KIND_RANK["other"]), index, url))
    if not usable:
        return None
    usable.sort(key=lambda item: (item[0], item[1]))
    return usable[0][2]


def _row_to_dict(row) -> dict:
    if isinstance(row, dict):
        return dict(row)
    # La conexión real usa dict_row; el fake de los tests puede entregar tuplas.
    keys = ("id", "slug", "name", "description", "source_urls", "google", "links")
    return dict(zip(keys, row))


def _assign(academy: dict, llm, brave_factory) -> tuple[dict | None, str]:
    """Devuelve (sede|None, estado) con estado en {'sede','ambigua','sin-sede'}.

    Orden: (0) google extranjero → sin sede (ni pre-paso ni LLM); (1) pre-paso
    determinista sobre la descripción; (2) Gemini Pasada A; (3) Pasada B.
    """

    if _has_foreign_google_address(academy):
        return None, "sin-sede"
    sede = _sede_from_text(academy)
    if sede is not None:
        return sede, "sede"
    if llm is None:
        return None, "sin-sede"
    sede, ambiguous_a = _pass_a(academy, llm)
    if sede is not None:
        return sede, "sede"
    brave = None
    if brave_factory is not None:
        brave = brave_factory(f'"{academy.get("name")}" Santiago comuna')
    sede, ambiguous_b = _pass_b(academy, brave, llm)
    if sede is not None:
        return sede, "sede"
    return None, "ambigua" if (ambiguous_a or ambiguous_b) else "sin-sede"


def _print_table(results: list[tuple[dict, dict | None, str]]) -> None:
    print(f"{'slug':<32}  {'comuna':<20}  {'dirección':<46}  fuente")
    for academy, sede, status in results:
        slug = academy.get("slug") or "-"
        if sede is not None:
            address = (sede["address"] or "-")[:46]
            source = sede["source_url"] or "SIN FUENTE (no se inserta)"
            if sede.get("via") == "texto":
                source = f"{source} [texto]"
            print(f"{slug:<32}  {sede['comuna']:<20}  {address:<46}  {source}")
        else:
            label = "AMBIGUA" if status == "ambigua" else "SIN SEDE"
            print(f"{slug:<32}  {label}")


def run(conn, llm=None, brave_factory=None, apply: bool = False) -> int:
    """Asigna sedes a las academias no cerradas sin ninguna academy_locations.

    Sin ``--apply``: imprime tabla y conteo, no escribe. Con ``--apply``:
    insert into academy_locations (...) region derivada del catálogo; idempotente
    (el query ya excluye las que tienen sede). Devuelve 0.
    """

    raw_rows = conn.execute(ACADEMIES_QUERY).fetchall()
    academies = [_row_to_dict(row) for row in raw_rows]

    if llm is None:
        print("aviso: sin LLM configurado; solo corre el pre-paso determinista")
    if brave_factory is None:
        print("aviso: sin Brave configurado; se omite la Pasada B")

    results: list[tuple[dict, dict | None, str]] = []
    for academy in academies:
        sede, status = _assign(academy, llm, brave_factory)
        results.append((academy, sede, status))

    inserted = 0
    if apply:
        for academy, sede, _ in results:
            if sede is None:
                continue
            if not sede.get("source_url"):
                # La compuerta exige fuente; no insertamos sedes sin evidencia.
                continue
            conn.execute(
                INSERT_LOCATION_SQL,
                (
                    academy["id"],
                    "Sede",
                    sede["address"],
                    sede["comuna"],
                    None,
                    None,
                    region_slug_for_comuna(sede["comuna"]),
                    sede["source_url"],
                ),
            )
            inserted += 1
        conn.commit()

    _print_table(results)
    con_sede = sum(1 for _, sede, _ in results if sede is not None and sede.get("source_url"))
    omitidas = sum(1 for _, sede, _ in results if sede is not None and not sede.get("source_url"))
    ambiguas = sum(1 for _, sede, status in results if sede is None and status == "ambigua")
    sin_sede = len(results) - con_sede - omitidas - ambiguas
    print(
        f"total={len(results)} con_sede={con_sede} "
        f"ambiguas={ambiguas} sin_sede={sin_sede} "
        f"omitidas_sin_fuente={omitidas}"
    )
    if apply:
        print(f"insertadas={inserted}")
        if omitidas:
            print(f"aviso: {omitidas} sede(s) sin source_url no se insertaron")
    return 0


class GeminiSedeLLM:
    """Cliente Gemini para extracción de sedes; misma estructura que GeminiLLM."""

    def __init__(
        self,
        api_key: str,
        http: HttpPost,
        models: list[str] | None = None,
    ):
        self.api_key = api_key
        self.http = http
        self.models = models or DEFAULT_MODELS

    def extract(self, prompt: str) -> dict | None:
        if not self.api_key:
            return None
        for model in self.models:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self.api_key}"
            )
            try:
                response = self.http.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"},
                    },
                )
            except Exception:
                return None
            status = getattr(response, "status_code", 0)
            if status == 429:
                return None
            if status in RETRYABLE_STATUS:
                continue
            if status != 200:
                return None
            try:
                body = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                return None
            return parse_llm_json(body)
        return None
