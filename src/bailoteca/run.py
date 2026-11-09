"""Orquestación de la corrida completa, el modo seco y el refresco puntual."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bailoteca.classify import classify
from bailoteca.config import Config
from bailoteca.db import (
    academy_id_by_slug,
    connect,
    insert_proposal,
    list_published,
    rejected_values,
    upsert_candidate,
)
from bailoteca.discover import collect
from bailoteca.enrich import CachedFetcher, HttpxFetcher, enrich
from bailoteca.links import check_published
from bailoteca.llm import GeminiLLM, HttpxPost
from bailoteca.models import Candidate
from bailoteca.normalize import candidate_key, normalize_handle
from bailoteca.propose import build_proposal
from bailoteca.report import render_weekly_report, stale_academies
from bailoteca.review import render_review
from bailoteca.sources.base import COMUNAS, Source
from bailoteca.sources.osm import OverpassSource
from bailoteca.sources.search import DuckDuckGoSource, build_queries
from bailoteca.sources.seed import load_seed


@dataclass
class RunSummary:
    discovered: int = 0
    new_candidates: int = 0
    proposals: int = 0
    needs_review: int = 0
    dead_links: int = 0
    duration_s: float = 0.0


class SeedSource:
    name = "seed"

    def __init__(self, path: Path = Path("data/seed.csv")):
        self.path = path

    def discover(self) -> list[Candidate]:
        if not self.path.exists():
            return []
        return load_seed(self.path)


def build_sources(config: Config) -> list[Source]:
    sources: list[Source] = []
    for name in config.sources:
        if name == "seed":
            sources.append(SeedSource())
        elif name == "search":
            import httpx

            sources.append(
                DuckDuckGoSource(build_queries(COMUNAS), httpx)
            )
        elif name == "osm":
            sources.append(OverpassSource())
    return sources


def parse_add_target(target: str) -> Candidate:
    target = target.strip()
    if target.startswith("@"):
        return Candidate(
            name=target,
            url=None,
            handle=normalize_handle(target),
            source="manual",
        )
    if target.startswith(("http://", "https://")):
        return Candidate(name=target, url=target, handle=None, source="manual")
    return Candidate(name=target, url=None, handle=None, source="manual")


def _text_for_classification(enriched) -> str:
    return " ".join(
        part for part in (enriched.description, enriched.text) if part
    )


def _write_reports(
    config: Config,
    summary: RunSummary,
    candidates: list[Candidate],
    drafts: list[tuple],
    dead: list[dict],
    stale: list[dict] | None = None,
) -> None:
    day = datetime.now(timezone.utc).date().isoformat()
    out = Path(config.reports_dir) / day
    out.mkdir(parents=True, exist_ok=True)

    (out / "candidates.json").write_text(
        json.dumps([asdict(candidate) for candidate in candidates], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "proposals.json").write_text(
        json.dumps(
            [
                {
                    "id": proposal_id,
                    "kind": draft.kind,
                    "confidence": draft.confidence,
                    "needs_review": draft.needs_review,
                    "payload": draft.payload,
                    "evidence": draft.evidence,
                }
                for draft, proposal_id in drafts
            ],
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    review_items = [
        {
            "id": proposal_id,
            "kind": draft.kind,
            "confidence": draft.confidence,
            "payload": draft.payload,
            "evidence": draft.evidence,
        }
        for draft, proposal_id in drafts
    ]
    (out / "review.md").write_text(render_review(review_items), encoding="utf-8")
    (out / "summary.md").write_text(
        render_weekly_report(summary, dead, stale or []), encoding="utf-8"
    )


def run(
    config: Config,
    *,
    dry_run: bool = False,
    sources: list[Source] | None = None,
    fetcher=None,
    llm=None,
) -> RunSummary:
    started = time.monotonic()
    if sources is None:
        sources = build_sources(config)
    if fetcher is None:
        fetcher = CachedFetcher(HttpxFetcher(), config.cache_dir)
    if llm is None and config.gemini_api_key:
        llm = GeminiLLM(config.gemini_api_key, HttpxPost())

    candidates = collect(sources)
    summary = RunSummary(discovered=len(candidates))
    drafts: list[tuple] = []
    dead: list[dict] = []
    stale: list[dict] = []

    conn = None
    if not dry_run:
        if not config.database_url:
            raise ValueError(
                "Falta DATABASE_URL. Configúrala en .env o usa run --dry-run."
            )
        conn = connect(config.database_url)

    try:
        for candidate in candidates:
            if conn is not None:
                key = candidate_key(
                    candidate.name, candidate.url, candidate.handle, candidate.comuna
                )
                existing_candidate = conn.execute(
                    "select id, status from candidates where key = %s", (key,)
                ).fetchone()
                if existing_candidate:
                    candidate_id = existing_candidate["id"]
                    if existing_candidate["status"] in ("published", "rejected"):
                        continue
                else:
                    candidate_id = upsert_candidate(conn, candidate)
                    summary.new_candidates += 1
            else:
                candidate_id = None

            enriched = enrich(candidate, fetcher)
            hits = classify(_text_for_classification(enriched), llm)

            existing = None
            rejections: set[tuple[str, str]] = set()
            if conn is not None and candidate_id is not None:
                existing_row = conn.execute(
                    """
                    select a.id, a.name, a.description, a.locations, a.links, a.styles,
                           a.verified_at
                    from academies a
                    join candidates c on c.id = a.id
                    where c.id = %s
                    """,
                    (candidate_id,),
                ).fetchone()
                if existing_row:
                    existing = {
                        "id": existing_row["id"],
                        "name": existing_row["name"],
                        "description": existing_row["description"],
                        "locations": existing_row["locations"],
                        "links": existing_row["links"],
                        "styles": existing_row["styles"],
                        "verified_at": existing_row["verified_at"],
                    }
                    rejections = rejected_values(conn, existing_row["id"])

            draft = build_proposal(candidate, enriched, hits, existing, rejections)
            if draft is None:
                continue
            if candidate_id is not None:
                draft = replace(draft, candidate_id=candidate_id)

            if conn is not None:
                proposal_id = insert_proposal(
                    conn,
                    candidate_id=draft.candidate_id,
                    academy_id=draft.academy_id,
                    kind=draft.kind,
                    payload=draft.payload,
                    evidence=draft.evidence,
                    confidence=draft.confidence,
                )
                if proposal_id is None:
                    continue
                conn.execute(
                    """
                    update candidates set status = 'proposed'
                    where id = %s and status = 'new'
                    """,
                    (candidate_id,),
                )
            else:
                proposal_id = draft.dedupe_key

            summary.proposals += 1
            if draft.needs_review:
                summary.needs_review += 1
            drafts.append((draft, proposal_id))

        if conn is not None:
            import httpx

            dead = check_published(conn, httpx)
            summary.dead_links = len(dead)
            stale = stale_academies(list_published(conn))
            conn.commit()
    finally:
        if conn is not None:
            conn.close()

    _write_reports(config, summary, candidates, drafts, dead, stale)
    summary.duration_s = round(time.monotonic() - started, 3)
    return summary


def _handle_from_instagram(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if (parts.hostname or "").lower().removeprefix("www.") != "instagram.com":
        return None
    return parts.path.strip("/").split("/")[0] or None


def refresh(config: Config, slug: str) -> RunSummary:
    if not config.database_url:
        raise ValueError("Falta DATABASE_URL para refrescar una academia.")
    conn = connect(config.database_url)
    try:
        academy_id = academy_id_by_slug(conn, slug)
        if academy_id is None:
            raise ValueError(f"no existe una academia publicada con slug {slug}")
        academy = next(
            item for item in list_published(conn) if item["id"] == academy_id
        )
        web = next(
            (link["url"] for link in academy["links"] if link["kind"] == "web"),
            None,
        )
        instagram = next(
            (link["url"] for link in academy["links"] if link["kind"] == "instagram"),
            None,
        )
        comuna = next(
            (loc["comuna"] for loc in academy["locations"] if loc.get("comuna")),
            None,
        )
        candidate = Candidate(
            name=academy["name"],
            url=web,
            handle=_handle_from_instagram(instagram),
            source="refresh",
            comuna=comuna,
        )
        fetcher = CachedFetcher(HttpxFetcher(), config.cache_dir)
        llm = (
            GeminiLLM(config.gemini_api_key, HttpxPost())
            if config.gemini_api_key
            else None
        )
        enriched = enrich(candidate, fetcher)
        hits = classify(_text_for_classification(enriched), llm)
        draft = build_proposal(
            candidate,
            enriched,
            hits,
            academy,
            rejected_values(conn, academy_id),
        )
        if draft is None:
            return RunSummary(discovered=1, duration_s=0.0)
        proposal_id = insert_proposal(
            conn,
            candidate_id=None,
            academy_id=academy_id,
            kind="update",
            payload=draft.payload,
            evidence=draft.evidence,
            confidence=draft.confidence,
        )
        conn.commit()
        return RunSummary(
            discovered=1,
            proposals=1 if proposal_id else 0,
            needs_review=1 if (proposal_id and draft.needs_review) else 0,
        )
    finally:
        conn.close()
