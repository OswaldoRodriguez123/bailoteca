"""Capa de lectura compartida por el parser y la API. No hace commit."""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, row_factory=dict_row)


def list_published(conn: psycopg.Connection) -> list[dict]:
    rows = conn.execute(
        """
        select
            a.id,
            a.slug,
            a.name,
            a.description,
            a.status,
            a.source_urls,
            a.created_at,
            a.updated_at,
            a.verified_at,
            coalesce(
                (
                    select json_agg(
                        json_build_object(
                            'label', al.label,
                            'address', al.address,
                            'comuna', al.comuna,
                            'lat', al.lat,
                            'lng', al.lng,
                            'source_url', al.source_url
                        )
                        order by al.label nulls first, al.comuna asc
                    )
                    from academy_locations al
                    where al.academy_id = a.id
                ),
                '[]'
            ) as locations,
            coalesce(
                (
                    select json_agg(
                        json_build_object(
                            'kind', alk.kind,
                            'url', alk.url
                        )
                        order by alk.kind asc, alk.url asc
                    )
                    from academy_links alk
                    where alk.academy_id = a.id
                ),
                '[]'
            ) as links,
            coalesce(
                (
                    select json_agg(
                        json_build_object(
                            'slug', s.slug,
                            'name', s.name,
                            'confidence', ast.confidence,
                            'evidence', ast.evidence
                        )
                        order by s.sort asc
                    )
                    from academy_styles ast
                    join styles s on s.id = ast.style_id
                    where ast.academy_id = a.id
                ),
                '[]'
            ) as styles
        from academies a
        order by a.name asc
        """
    ).fetchall()
    return rows


def academy_id_by_slug(conn: psycopg.Connection, slug: str) -> str | None:
    row = conn.execute(
        "select id from academies where slug = %s",
        (slug,),
    ).fetchone()
    return row["id"] if row else None
