"""Validación, aprobación y publicación de propuestas."""

from __future__ import annotations

from collections import Counter
from typing import Literal

import psycopg
from bailoteca_shared.regions import region_slug_for_comuna
from pydantic import BaseModel, ConfigDict, Field

from bailoteca.db import record_field_rejections
from bailoteca.normalize import slugify
from bailoteca.propose import field_value_hash

LINK_KINDS = (
    "web",
    "instagram",
    "facebook",
    "tiktok",
    "whatsapp",
    "phone",
    "email",
)
STYLE_SLUGS = ("salsa-cubana", "salsa-linea", "mambo", "bachata")


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    address: str | None = None
    comuna: str | None = None
    lat: float | None = None
    lng: float | None = None
    source_url: str | None = None


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "web", "instagram", "facebook", "tiktok", "whatsapp", "phone", "email"
    ]
    url: str


class StyleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Literal["salsa-cubana", "salsa-linea", "mambo", "bachata"]
    confidence: float | None = None
    evidence: str | None = None
    disputed: bool = False


class ProposalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    locations: list[LocationIn] = []
    links: list[LinkIn] = []
    styles: list[StyleIn] = []


def validate_payload(payload: dict) -> dict:
    return ProposalPayload.model_validate(payload).model_dump()


def _scalar_flat(payload: dict) -> dict:
    """Campos de valor único: name/description. (Links y sedes se comparan
    como multisets en ``replaced_pairs``; aplanarlos pierde rechazos.)"""
    flat: dict = {}
    for key in ("name", "description"):
        if key in payload:
            flat[key] = payload[key]
    for style in payload.get("styles") or []:
        if style.get("slug"):
            flat[f"style:{style['slug']}"] = style["slug"]
    return flat


def _locations(payload: dict) -> list[dict]:
    locs = payload.get("locations")
    if locs:
        return list(locs)
    if payload.get("address") or payload.get("comuna"):
        # forma legacy: address/comuna sueltos en el payload
        return [{"address": payload.get("address"), "comuna": payload.get("comuna")}]
    return []


def _location_pairs(payload: dict) -> list[tuple[str | None, str | None]]:
    pairs = []
    for loc in _locations(payload):
        address, comuna = loc.get("address"), loc.get("comuna")
        if address or comuna:
            pairs.append((address, comuna))
    return pairs


def _link_counter(payload: dict) -> "Counter[tuple[str, str]]":
    counter: Counter[tuple[str, str]] = Counter()
    links = payload.get("links")
    if links:
        for link in links:
            kind, url = link.get("kind"), link.get("url")
            if kind and url:
                counter[(kind, url)] += 1
    else:
        for kind in LINK_KINDS:
            if payload.get(kind):
                counter[(kind, payload[kind])] += 1
    return counter


def replaced_pairs(proposed: dict, approved: dict) -> list[tuple[str, str]]:
    proposed_flat = _scalar_flat(proposed)
    approved_flat = _scalar_flat(approved)
    pairs: list[tuple[str, str]] = []
    for field, value in proposed_flat.items():
        if approved_flat.get(field) != value:
            pairs.append((field, field_value_hash(field, value)))

    # Sedes: con una sede propuesta se comparan address y comuna por separado
    # contra la primera del payload aprobado (comportamiento previo); con varias
    # sedes la comuna es compartida, así que solo se graba el address de cada
    # sede descartada (evita rechazar comunas legítimas).
    proposed_locs = _location_pairs(proposed)
    approved_locs = _location_pairs(approved)
    if len(proposed_locs) <= 1:
        approved_addrs = {a for a, _ in approved_locs}
        approved_comunas = {c for _, c in approved_locs}
        for address, comuna in proposed_locs:
            if address and address not in approved_addrs:
                pairs.append(("address", field_value_hash("address", address)))
            if comuna and comuna not in approved_comunas:
                pairs.append(("comuna", field_value_hash("comuna", comuna)))
    else:
        approved_addrs = {a for a, _ in _location_pairs(approved)}
        seen: set[str] = set()
        for addr, _comuna in _location_pairs(proposed):
            if addr and addr not in approved_addrs and addr not in seen:
                pairs.append(("address", field_value_hash("address", addr)))
                seen.add(addr)

    # Links: multiset — cada link propuesto descartado/reemplazado se graba,
    # sin importar que comparta kind con otros.
    proposed_links = _link_counter(proposed)
    approved_links = set(_link_counter(approved))
    seen: set[tuple[str, str]] = set()
    for (kind, url) in proposed_links:
        if (kind, url) in seen:
            continue
        seen.add((kind, url))
        if (kind, url) not in approved_links:
            pairs.append((kind, field_value_hash(kind, url)))
    return pairs


def _unique_slug(conn: psycopg.Connection, name: str) -> str:
    base = slugify(name) or "academia"
    slug = base
    suffix = 2
    while conn.execute(
        "select 1 from academies where slug = %s", (slug,)
    ).fetchone():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def location_values(loc: dict, academy_id: str) -> tuple:
    comuna = loc.get("comuna")
    return (
        academy_id,
        loc.get("label"),
        loc.get("address"),
        comuna,
        loc.get("lat"),
        loc.get("lng"),
        region_slug_for_comuna(comuna),
        loc.get("source_url"),
    )


def _write_relations(
    conn: psycopg.Connection, academy_id: str, payload: dict
) -> None:
    conn.execute(
        "delete from academy_locations where academy_id = %s", (academy_id,)
    )
    for location in payload["locations"]:
        conn.execute(
            """
            insert into academy_locations
              (academy_id, label, address, comuna, lat, lng, region, source_url)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            location_values(location, academy_id),
        )

    conn.execute("delete from academy_links where academy_id = %s", (academy_id,))
    for link in payload["links"]:
        conn.execute(
            """
            insert into academy_links (academy_id, kind, url)
            values (%s, %s, %s)
            """,
            (academy_id, link["kind"], link["url"]),
        )

    conn.execute("delete from academy_styles where academy_id = %s", (academy_id,))
    for style in payload["styles"]:
        style_row = conn.execute(
            "select id from styles where slug = %s", (style["slug"],)
        ).fetchone()
        if style_row is None:
            continue
        conn.execute(
            """
            insert into academy_styles (academy_id, style_id, confidence, evidence)
            values (%s, %s, %s, %s)
            """,
            (
                academy_id,
                style_row["id"],
                style.get("confidence"),
                style.get("evidence"),
            ),
        )


def approve(
    conn: psycopg.Connection,
    proposal_id: str,
    payload: dict | None = None,
    *,
    verify: bool = True,
) -> str:
    row = conn.execute(
        """
        select id, candidate_id, academy_id, kind, payload, status
        from proposals where id = %s
        """,
        (proposal_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"propuesta no encontrada: {proposal_id}")

    original = row["payload"] or {}
    approved = validate_payload(payload if payload is not None else original)
    data = approved

    academy_id = row["academy_id"]
    if academy_id is None:
        slug = _unique_slug(conn, data["name"])
        created = conn.execute(
            """
            insert into academies (slug, name, description, verified_at)
            values (%s, %s, %s, case when %s then now() else null end)
            returning id
            """,
            (slug, data["name"], data["description"], verify),
        ).fetchone()
        academy_id = created["id"]
    else:
        conn.execute(
            """
            update academies set
              name = %s,
              description = %s,
              updated_at = now(),
              verified_at = case when %s then now() else null end
            where id = %s
            """,
            (data["name"], data["description"], verify, academy_id),
        )

    _write_relations(conn, academy_id, data)

    pairs = replaced_pairs(original, data)
    if pairs:
        record_field_rejections(conn, academy_id, pairs)

    conn.execute(
        """
        update proposals set status = 'approved', reviewed_at = now()
        where id = %s
        """,
        (proposal_id,),
    )
    if row["candidate_id"]:
        conn.execute(
            "update candidates set status = 'published' where id = %s",
            (row["candidate_id"],),
        )

    return academy_id


def reject(conn: psycopg.Connection, proposal_id: str) -> None:
    # Get candidate_id first to mark it rejected too
    row = conn.execute(
        "select candidate_id from proposals where id = %s",
        (proposal_id,),
    ).fetchone()
    if row and row["candidate_id"]:
        conn.execute(
            "update candidates set status = 'rejected' where id = %s",
            (row["candidate_id"],),
        )
    conn.execute(
        """
        update proposals set status = 'rejected', reviewed_at = now()
        where id = %s
        """,
        (proposal_id,),
    )


def unpublish(conn: psycopg.Connection, slug: str) -> dict:
    """Despublica una academia: borra la fila (cascade a sedes/links/estilos/\n    field_rejections) y marca como rejected la(s) propuesta(s) y candidato(s)\n    que la originaron. Devuelve un resumen."""
    row = conn.execute(
        "select id, name, slug from academies where slug = %s", (slug,)
    ).fetchone()
    if row is None:
        raise ValueError(f"academia no encontrada: {slug}")
    academy_id = row["id"]

    proposals = conn.execute(
        """
        select id, candidate_id from proposals
        where academy_id = %s and status = 'approved'
        """,
        (academy_id,),
    ).fetchall()

    candidate_ids = [p["candidate_id"] for p in proposals if p["candidate_id"]]
    for p in proposals:
        conn.execute(
            """
            update proposals set status = 'rejected', reviewed_at = now()
            where id = %s
            """,
            (p["id"],),
        )
    if candidate_ids:
        conn.execute(
            """
            update candidates set status = 'rejected'
            where id = any(%s::uuid[]) and status = 'published'
            """,
            (candidate_ids,),
        )

    conn.execute("delete from academies where id = %s", (academy_id,))

    return {
        "slug": slug,
        "name": row["name"],
        "academy_id": str(academy_id),
        "proposals_rejected": len(proposals),
        "candidates_rejected": len(candidate_ids),
    }
    # Get candidate_id first to mark it rejected too
    row = conn.execute(
        "select candidate_id from proposals where id = %s",
        (proposal_id,),
    ).fetchone()
    if row and row["candidate_id"]:
        conn.execute(
            "update candidates set status = 'rejected' where id = %s",
            (row["candidate_id"],),
        )
    conn.execute(
        """
        update proposals set status = 'rejected', reviewed_at = now()
        where id = %s
        """,
        (proposal_id,),
    )
