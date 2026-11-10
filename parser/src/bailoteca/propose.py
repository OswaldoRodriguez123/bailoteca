"""Construcción de propuestas y supresión de valores ya rechazados."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from bailoteca.classify import REVIEW_CONFIDENCE, needs_review
from bailoteca.enrich import Enriched
from bailoteca.llm import StyleHit
from bailoteca.models import Candidate
from bailoteca.normalize import candidate_key, payload_hash


@dataclass(frozen=True)
class ProposalDraft:
    kind: str
    candidate_id: str | None
    academy_id: str | None
    payload: dict
    evidence: dict
    confidence: float
    dedupe_key: str
    changes: list[str] = field(default_factory=list)
    needs_review: bool = False


def field_value_hash(field: str, value: object) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def style_payload(hits: list[StyleHit]) -> list[dict]:
    kept = [hit for hit in hits if hit.confidence >= REVIEW_CONFIDENCE]
    kept.sort(key=lambda hit: hit.slug)
    return [
        {"slug": hit.slug, "confidence": hit.confidence, "evidence": hit.quote}
        for hit in kept
    ]


def _payload_view(payload: dict) -> dict:
    locations = payload.get("locations") or []
    location = locations[0] if locations else {}
    return {
        "name": payload.get("name"),
        "description": payload.get("description"),
        "address": location.get("address"),
        "comuna": location.get("comuna"),
        "links": {
            (link.get("kind"), link.get("url"))
            for link in payload.get("links") or []
        },
        "styles": {
            style.get("slug") for style in payload.get("styles") or []
        },
    }


def _existing_view(existing: dict) -> dict:
    locations = existing.get("locations") or []
    location = locations[0] if locations else existing

    if existing.get("links") is not None:
        links = {
            (link.get("kind"), link.get("url"))
            for link in existing.get("links") or []
        }
    else:
        links = set()
        for kind in ("web", "instagram", "facebook", "tiktok", "whatsapp", "phone", "email"):
            value = existing.get(kind)
            if isinstance(value, str):
                links.add((kind, value))
            elif isinstance(value, list):
                for url in value:
                    links.add((kind, url))

    return {
        "name": existing.get("name"),
        "description": existing.get("description"),
        "address": location.get("address"),
        "comuna": location.get("comuna"),
        "links": links,
        "styles": {
            style.get("slug") for style in existing.get("styles") or []
        },
    }


def _build_payload(
    candidate: Candidate,
    enriched: Enriched | None,
    hits: list[StyleHit],
    rejections: set[tuple[str, str]],
    existing: dict | None = None,
) -> dict:
    payload: dict = {"name": candidate.name}

    if enriched is None:
        links = []
        if candidate.url:
            links.append({"kind": "web", "url": candidate.url})
        if candidate.handle:
            links.append(
                {"kind": "instagram", "url": f"https://instagram.com/{candidate.handle}"}
            )
        payload["locations"] = []
        payload["links"] = links
        payload["styles"] = style_payload(hits)
        return payload

    candidate_description = None
    raw = getattr(candidate, "raw", None)
    if isinstance(raw, dict):
        candidate_description = raw.get("description")

    if enriched.description:
        payload["description"] = enriched.description
    elif candidate_description:
        payload["description"] = candidate_description
    elif existing and existing.get("description"):
        payload["description"] = existing["description"]

    view = _existing_view(existing) if existing is not None else None

    location: dict = {}
    addr_rejected = (
        "address",
        field_value_hash("address", enriched.address) if enriched.address else "",
    ) in rejections
    if enriched.address and not addr_rejected:
        location["address"] = enriched.address
    elif view and view.get("address"):
        location["address"] = view["address"]

    comuna_rejected = (
        "comuna",
        field_value_hash("comuna", enriched.comuna) if enriched.comuna else "",
    ) in rejections
    if enriched.comuna and not comuna_rejected:
        location["comuna"] = enriched.comuna
    elif view and view.get("comuna"):
        location["comuna"] = view["comuna"]

    payload["locations"] = [location] if location else []

    links = []
    for kind, urls in enriched.links.items():
        for url in urls:
            if (kind, field_value_hash(kind, url)) in rejections:
                continue
            links.append({"kind": kind, "url": url})
    links.sort(key=lambda link: (link["kind"], link["url"]))
    if links:
        payload["links"] = links
    elif existing and existing.get("links"):
        payload["links"] = existing["links"]

    styles = []
    for style in style_payload(hits):
        slug = style["slug"]
        if ("style:" + slug, field_value_hash("style:" + slug, slug)) in rejections:
            continue
        styles.append(style)
    if styles:
        payload["styles"] = styles
    elif existing and existing.get("styles"):
        payload["styles"] = [
            {
                "slug": style["slug"],
                "confidence": style.get("confidence"),
                "evidence": style.get("evidence"),
            }
            for style in existing["styles"]
        ]

    return payload


def build_proposal(
    candidate: Candidate,
    enriched: Enriched | None,
    hits: list[StyleHit],
    existing: dict | None,
    rejections: set[tuple[str, str]],
) -> ProposalDraft | None:
    payload = _build_payload(candidate, enriched, hits, rejections, existing)
    proposed = _payload_view(payload)

    if existing is not None:
        current = _existing_view(existing)
        fields = ("name", "description", "address", "comuna", "links", "styles")
        changes = [field for field in fields if proposed[field] != current[field]]
        if not changes:
            return None
    else:
        changes = ["create"]

    kind = "update" if existing is not None else "create"
    academy_id = existing.get("id") if existing is not None else None
    destination = academy_id or candidate_key(
        candidate.name, candidate.url, candidate.handle, candidate.comuna
    )
    dedupe_key = hashlib.sha256(
        f"{kind}|{destination}|{payload_hash(payload)}".encode("utf-8")
    ).hexdigest()

    confidences = [style["confidence"] for style in payload.get("styles", [])]
    confidence = min(confidences) if confidences else 0.0
    review = enriched is None or any(needs_review(hit) for hit in hits) or not payload.get("styles")

    return ProposalDraft(
        kind=kind,
        candidate_id=None,
        academy_id=academy_id,
        payload=payload,
        evidence=enriched.evidence if enriched is not None else {},
        confidence=confidence,
        dedupe_key=dedupe_key,
        changes=changes,
        needs_review=review,
    )
