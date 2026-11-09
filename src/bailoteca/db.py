"""Acceso a Postgres. Ninguna función hace commit; la CLI cierra la transacción."""

from __future__ import annotations

import hashlib

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from bailoteca.models import Candidate
from bailoteca.normalize import candidate_key, payload_hash


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, row_factory=dict_row)


def upsert_candidate(conn: psycopg.Connection, cand: Candidate) -> str:
    key = candidate_key(cand.name, cand.url, cand.handle, cand.comuna)
    row = conn.execute(
        """
        insert into candidates (key, name, url, handle, source, comuna, raw)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (key) do update set
          name = excluded.name,
          url = excluded.url,
          handle = excluded.handle,
          comuna = excluded.comuna
        returning id
        """,
        (
            key,
            cand.name,
            cand.url,
            cand.handle,
            cand.source,
            cand.comuna,
            Jsonb(cand.raw),
        ),
    ).fetchone()
    return row["id"]


def proposal_dedupe_key(
    kind: str,
    destination_id: str | None,
    payload: dict,
) -> str:
    raw = f"{kind}|{destination_id}|{payload_hash(payload)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def insert_proposal(
    conn: psycopg.Connection,
    *,
    candidate_id: str | None,
    academy_id: str | None,
    kind: str,
    payload: dict,
    evidence: dict,
    confidence: float,
) -> str | None:
    dedupe_key = proposal_dedupe_key(kind, academy_id or candidate_id, payload)
    row = conn.execute(
        """
        insert into proposals
          (candidate_id, academy_id, kind, dedupe_key, payload, evidence, confidence)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (dedupe_key) do nothing
        returning id
        """,
        (
            candidate_id,
            academy_id,
            kind,
            dedupe_key,
            Jsonb(payload),
            Jsonb(evidence),
            confidence,
        ),
    ).fetchone()
    return row["id"] if row else None


def pending_proposals(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        """
        select id, candidate_id, academy_id, kind, payload, evidence, confidence
        from proposals
        where status = 'pending'
        order by confidence asc nulls last, created_at asc
        """
    ).fetchall()


def record_field_rejections(
    conn: psycopg.Connection,
    academy_id: str,
    pairs: list[tuple[str, str]],
) -> int:
    if not pairs:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into field_rejections (academy_id, field, value_hash)
            values (%s, %s, %s)
            on conflict do nothing
            """,
            [(academy_id, field, value_hash) for field, value_hash in pairs],
        )
        return cur.rowcount


def rejected_values(
    conn: psycopg.Connection,
    academy_id: str,
) -> set[tuple[str, str]]:
    rows = conn.execute(
        "select field, value_hash from field_rejections where academy_id = %s",
        (academy_id,),
    ).fetchall()
    return {(row["field"], row["value_hash"]) for row in rows}


def mark_proposal(conn: psycopg.Connection, proposal_id: str, status: str) -> None:
    conn.execute(
        """
        update proposals
        set status = %s, reviewed_at = now()
        where id = %s
        """,
        (status, proposal_id),
    )


def list_published(conn: psycopg.Connection) -> list[dict]:
    academies = conn.execute(
        """
        select id, slug, name, description, status, source_urls,
               created_at, updated_at, verified_at
        from academies
        order by name asc
        """
    ).fetchall()
    result = []
    for academy in academies:
        academy_id = academy["id"]
        locations = conn.execute(
            """
            select label, address, comuna, lat, lng, source_url
            from academy_locations where academy_id = %s
            order by label nulls first, comuna asc
            """,
            (academy_id,),
        ).fetchall()
        links = conn.execute(
            """
            select kind, url from academy_links where academy_id = %s
            order by kind asc, url asc
            """,
            (academy_id,),
        ).fetchall()
        styles = conn.execute(
            """
            select s.slug, s.name, a.confidence, a.evidence
            from academy_styles a
            join styles s on s.id = a.style_id
            where a.academy_id = %s
            order by s.sort asc
            """,
            (academy_id,),
        ).fetchall()
        result.append(
            {**academy, "locations": locations, "links": links, "styles": styles}
        )
    return result


def academy_id_by_slug(conn: psycopg.Connection, slug: str) -> str | None:
    row = conn.execute(
        "select id from academies where slug = %s",
        (slug,),
    ).fetchone()
    return row["id"] if row else None
