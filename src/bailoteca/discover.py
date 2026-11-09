from __future__ import annotations

from dataclasses import replace

from bailoteca.models import Candidate
from bailoteca.normalize import candidate_key, normalize_name
from bailoteca.sources.base import Source


def _loose_key(name: str, comuna: str | None) -> str:
    return f"{normalize_name(name)}|{normalize_name(comuna) if comuna else ''}"


def _loose_match_key(existing: Candidate, candidate: Candidate) -> bool:
    """Match by name; if both have comuna, require it to match."""
    if normalize_name(existing.name) != normalize_name(candidate.name):
        return False
    if existing.comuna and candidate.comuna:
        return normalize_name(existing.comuna) == normalize_name(candidate.comuna)
    return True


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
                    url=existing.url or candidate.url,
                    handle=existing.handle or candidate.handle,
                    comuna=existing.comuna or candidate.comuna,
                    raw={**existing.raw, **candidate.raw},
                )
            else:
                # Try loose match by name (+ comuna if both have it) for cross-source dedupe
                matched = None
                for existing_key, existing in merged.items():
                    if _loose_match_key(existing, candidate):
                        matched = existing_key
                        break
                if matched is not None:
                    existing = merged[matched]
                    # Replace with merged candidate under the new (more specific) key
                    merged[matched] = replace(
                        existing,
                        url=existing.url or candidate.url,
                        handle=existing.handle or candidate.handle,
                        comuna=existing.comuna or candidate.comuna,
                        raw={**existing.raw, **candidate.raw},
                    )
                else:
                    merged[key] = candidate
    return list(merged.values())
