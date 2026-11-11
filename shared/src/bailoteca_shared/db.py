"""Capa de lectura compartida por el parser y la API. No hace commit."""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


_ACADEMY_SELECT = """
    select
        a.id::text as id,
        a.slug,
        a.name,
        a.description,
        a.status,
        a.source_urls,
        a.created_at,
        a.updated_at,
        a.verified_at,
        a.cover_url,
        a.cover_source,
        a.cover_fetched_at,
        a.google,
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
"""


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, row_factory=dict_row)


def _like_pattern(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def _academy_filters(
    comuna: str | None = None,
    style: str | None = None,
    q: str | None = None,
) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []

    if comuna:
        clauses.append(
            "exists (select 1 from academy_locations al "
            "where al.academy_id = a.id and lower(al.comuna) = lower(%s))"
        )
        params.append(comuna)

    if style:
        clauses.append(
            "exists (select 1 from academy_styles ast "
            "join styles s on s.id = ast.style_id "
            "where ast.academy_id = a.id and s.slug = %s)"
        )
        params.append(style)

    if q:
        pattern = _like_pattern(q)
        clauses.append(
            "(a.name ilike %s escape '\\' or "
            "coalesce(a.description, '') ilike %s escape '\\')"
        )
        params.extend([pattern, pattern])

    if not clauses:
        return "", []

    return " where " + " and ".join(clauses), params


def _academy_rows(
    conn: psycopg.Connection,
    where: str = "",
    params: tuple = (),
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    sql = f"{_ACADEMY_SELECT}{where} order by a.name asc"
    query_params = list(params)
    if limit is not None:
        sql += " limit %s offset %s"
        query_params.extend([limit, offset])
    return conn.execute(sql, tuple(query_params)).fetchall()


def list_published(conn: psycopg.Connection) -> list[dict]:
    return _academy_rows(conn)


def list_academies(
    conn: psycopg.Connection,
    *,
    comuna: str | None = None,
    style: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where, params = _academy_filters(comuna=comuna, style=style, q=q)
    total_row = conn.execute(
        f"select count(*) as total from academies a{where}",
        tuple(params),
    ).fetchone()
    total = total_row["total"] if total_row else 0
    rows = _academy_rows(conn, where, tuple(params), limit=limit, offset=offset)
    return rows, total


def get_academy_by_slug(
    conn: psycopg.Connection, slug: str
) -> dict | None:
    rows = _academy_rows(conn, " where a.slug = %s", (slug,), limit=1)
    return rows[0] if rows else None


def list_styles(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        "select slug, name, sort from styles order by sort asc, name asc"
    ).fetchall()


def list_comunas(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        "select distinct comuna from academy_locations "
        "where comuna is not null and btrim(comuna) <> '' "
        "order by comuna asc"
    ).fetchall()
    return [row["comuna"] for row in rows]


def academy_id_by_slug(conn: psycopg.Connection, slug: str) -> str | None:
    row = conn.execute(
        "select id::text as id from academies where slug = %s",
        (slug,),
    ).fetchone()
    return row["id"] if row else None
