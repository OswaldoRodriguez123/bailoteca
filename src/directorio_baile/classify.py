"""Clasificación de estilos de salsa: reglas locales + refuerzo opcional del LLM."""

from __future__ import annotations

from directorio_baile.llm import LLM, StyleHit
from directorio_baile.normalize import strip_accents

AUTO_CONFIDENCE = 0.85
REVIEW_CONFIDENCE = 0.60

VALID_SLUGS = ["salsa-cubana", "salsa-linea", "mambo"]

# (frase normalizada, slug, confianza) en orden de evaluación.
RULE_HITS: list[tuple[str, str, float]] = [
    ("salsa cubana", "salsa-cubana", 0.9),
    ("salsa casino", "salsa-cubana", 0.9),
    ("rueda de casino", "salsa-cubana", 0.9),
    ("casino", "salsa-cubana", 0.65),
    ("salsa en linea", "salsa-linea", 0.9),
    ("salsa on1", "salsa-linea", 0.9),
    ("salsa on2", "salsa-linea", 0.9),
    ("on1", "salsa-linea", 0.65),
    ("on2", "salsa-linea", 0.65),
    ("salsa mambo", "mambo", 0.9),
    ("mambo", "mambo", 0.65),
]


def _normalize(text: str) -> str:
    return strip_accents(text).lower()


def rule_hits(text: str) -> list[StyleHit]:
    normalized = _normalize(text)
    best: dict[str, StyleHit] = {}
    order: list[str] = []
    for phrase, slug, confidence in RULE_HITS:
        if phrase not in normalized:
            continue
        if slug not in best:
            best[slug] = StyleHit(slug, confidence, phrase)
            order.append(slug)
        elif confidence > best[slug].confidence:
            best[slug] = StyleHit(slug, confidence, phrase, best[slug].disputed)
    return [best[slug] for slug in order]


def needs_review(hit: StyleHit) -> bool:
    return hit.disputed or hit.confidence < AUTO_CONFIDENCE


def merge_hits(
    rules: list[StyleHit],
    llm: list[StyleHit] | None,
) -> list[StyleHit]:
    merged = {hit.slug: hit for hit in rules}
    order = [hit.slug for hit in rules]
    rule_confidence = {hit.slug: hit.confidence for hit in rules}

    for hit in llm or []:
        existing = merged.get(hit.slug)
        if existing is None:
            merged[hit.slug] = hit
            order.append(hit.slug)
            continue
        disputed = existing.disputed or hit.disputed
        if rule_confidence.get(hit.slug, 0.0) >= 0.9 and hit.confidence < 0.5:
            disputed = True
        if hit.confidence > existing.confidence:
            merged[hit.slug] = StyleHit(
                hit.slug, hit.confidence, hit.quote, disputed
            )
        else:
            merged[hit.slug] = StyleHit(
                existing.slug, existing.confidence, existing.quote, disputed
            )
    return [merged[slug] for slug in order]


def classify(text: str, llm: LLM | None) -> list[StyleHit]:
    rules = rule_hits(text)
    if llm is None:
        return rules
    try:
        raw = llm.classify_styles(text, VALID_SLUGS)
    except Exception:
        return rules
    if not raw:
        return rules

    normalized = _normalize(text)
    filtered: list[StyleHit] = []
    for hit in raw:
        if hit.slug not in VALID_SLUGS:
            continue
        if not 0.0 <= hit.confidence <= 1.0:
            continue
        if not hit.quote:
            continue
        if _normalize(hit.quote) not in normalized:
            continue
        filtered.append(hit)
    return merge_hits(rules, filtered)
