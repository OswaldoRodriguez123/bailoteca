from __future__ import annotations

from dataclasses import dataclass, replace

from bailoteca.models import Candidate
from bailoteca.normalize import candidate_key, normalize_name
from bailoteca.sources.base import Source
from bailoteca.sources.filters import filter_noise


@dataclass(frozen=True)
class CollectResult:
    candidates: list[Candidate]
    filtered_rules: int


def _loose_key(name: str, comuna: str | None) -> str:
    return f"{normalize_name(name)}|{normalize_name(comuna) if comuna else ''}"


def _loose_match_key(existing: Candidate, candidate: Candidate) -> bool:
    """Match by name; if both have comuna, require it to match."""
    if normalize_name(existing.name) != normalize_name(candidate.name):
        return False
    if existing.comuna and candidate.comuna:
        return normalize_name(existing.comuna) == normalize_name(candidate.comuna)
    return True


def collect(sources: list[Source]) -> CollectResult:
    discovered: list[Candidate] = []
    for source in sources:
        discovered.extend(source.discover())
    kept, dropped = filter_noise(discovered)

    merged: dict[str, Candidate] = {}
    for candidate in kept:
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
    return CollectResult(candidates=list(merged.values()), filtered_rules=dropped)
