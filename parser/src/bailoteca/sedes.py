"""Backfill asistido de sedes para academias publicadas sin sede.

Pasada A: extrae comuna + dirección desde nombre, descripción y (solo si
``looks_chilean``) la dirección de Google Maps. Pasada B: busca en Brave
(``f'"{name}" Santiago comuna'``, una query, num=3) y extrae por candidato.
Compuerta (``extract_rm_comuna``): match normalizado EXACTO contra las comunas
RM del catálogo oficial; cualquier otra cosa → None (sin sede). Con ``--apply``
inserta en ``academy_locations`` (label='Sede', lat/lng null, region derivada
del catálogo); por defecto solo imprime el plan (dry-run).
"""

from __future__ import annotations

import json
import re
import sys
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
select a.id::text, a.slug, a.name, a.description, a.source_urls, a.google
from academies a
where a.status='active' and not exists (select 1 from academy_locations al where al.academy_id=a.id)
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
    return (
        {
            "address": " ".join(address.split()),
            "comuna": comuna,
            "source_url": source_urls[0] if source_urls else None,
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
        if not description.strip():
            continue
        snippet = f"{candidate.name}: {description}"
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


def _row_to_dict(row) -> dict:
    if isinstance(row, dict):
        return dict(row)
    # La conexión real usa dict_row; el fake de los tests puede entregar tuplas.
    keys = ("id", "slug", "name", "description", "source_urls", "google")
    return dict(zip(keys, row))


def _assign(academy: dict, llm, brave_factory) -> tuple[dict | None, str]:
    """Devuelve (sede|None, estado) con estado en {'sede','ambigua','sin-sede'}."""

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
            address = sede["address"][:46]
            print(f"{slug:<32}  {sede['comuna']:<20}  {address:<46}  {sede['source_url']}")
        else:
            label = "AMBIGUA" if status == "ambigua" else "SIN SEDE"
            print(f"{slug:<32}  {label}")


def run(conn, llm=None, brave_factory=None, apply: bool = False) -> int:
    """Asigna sedes a las academias activas sin ninguna academy_locations.

    Sin ``--apply``: imprime tabla y conteo, no escribe. Con ``--apply``:
    insert into academy_locations (...) region derivada del catálogo; idempotente
    (el query ya excluye las que tienen sede). Devuelve 0.
    """

    raw_rows = conn.execute(ACADEMIES_QUERY).fetchall()
    academies = [_row_to_dict(row) for row in raw_rows]

    if llm is None:
        print("aviso: sin LLM configurado; todas las academias quedan SIN SEDE")
    if brave_factory is None:
        print("aviso: sin Brave configurado; se omite la Pasada B")

    results: list[tuple[dict, dict | None, str]] = []
    for academy in academies:
        sede, status = _assign(academy, llm, brave_factory)
        results.append((academy, sede, status))

    inserted = 0
    skipped_no_source = 0
    if apply:
        for academy, sede, _ in results:
            if sede is None:
                continue
            if not sede.get("source_url"):
                # La compuerta exige fuente; no insertamos sedes sin evidencia.
                skipped_no_source += 1
                print(
                    f"aviso: {academy.get('slug')} sin source_url; no se inserta",
                    file=sys.stderr,
                )
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
    con_sede = sum(1 for _, sede, _ in results if sede is not None)
    ambiguas = sum(1 for _, sede, status in results if sede is None and status == "ambigua")
    sin_sede = len(results) - con_sede - ambiguas
    print(
        f"total={len(results)} con_sede={con_sede} "
        f"ambiguas={ambiguas} sin_sede={sin_sede}"
    )
    if apply:
        print(f"insertadas={inserted}")
        if skipped_no_source:
            print(f"omitidas_sin_fuente={skipped_no_source}")
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
