"""Resumen de cobertura de OpenStreetMap para decidir si se conserva la fuente."""

from __future__ import annotations

from collections import Counter

from directorio_baile.models import Candidate


def summarize(candidates: list[Candidate]) -> dict:
    comunas = Counter(
        candidate.comuna for candidate in candidates if candidate.comuna
    )
    return {
        "named": len(candidates),
        "with_address": sum(
            1 for candidate in candidates if candidate.raw.get("address")
        ),
        "with_web_or_ig": sum(
            1 for candidate in candidates if candidate.url or candidate.handle
        ),
        "comunas": dict(sorted(comunas.items())),
    }
