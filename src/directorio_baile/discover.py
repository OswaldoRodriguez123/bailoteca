from __future__ import annotations

from dataclasses import replace

from directorio_baile.models import Candidate
from directorio_baile.normalize import candidate_key
from directorio_baile.sources.base import Source


def collect(sources: list[Source]) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for source in sources:
        for candidate in source.discover():
            key = candidate_key(
                candidate.name,
                candidate.url,
                candidate.handle,
                candidate.comuna,
            )
            if key in merged:
                existing = merged[key]
                merged[key] = replace(
                    existing,
                    raw={**existing.raw, **candidate.raw},
                )
            else:
                merged[key] = candidate
    return list(merged.values())
