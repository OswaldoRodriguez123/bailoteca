from pathlib import Path
from types import SimpleNamespace

import pytest

from bailoteca_shared.db import SORTS, _academy_order, list_academies


def test_sorts_and_migration_are_additive():
    assert SORTS == ("destacadas", "nombre", "nuevas", "cercanas")
    sql = Path(__file__).parents[2].joinpath(
        "supabase/migrations/0011_academy_social.sql"
    ).read_text(encoding="utf-8")
    assert "add column if not exists social_followers integer" in sql
    assert "add column if not exists social_network text" in sql


def test_destacadas_combines_the_three_signals():
    sql, params = _academy_order()
    assert "0.55" in sql and "0.25" in sql and "0.20" in sql
    assert "avg(" in sql and "over ()" in sql and "a.social_followers" in sql
    assert "a.name asc" in sql and params == []
    # Google ausente: rating 0 sin castear null.
    assert "when a.google->>'rating' is null then 0" in sql
    # Conjunto sin ratings/seguidores: máximos nunca null ni 0.
    assert "coalesce(avg(" in sql and "greatest(1," in sql


def test_destacadas_tolerates_malformed_google_json():
    # Un solo registro con rating/reviews no numérico no debe provocar un 500:
    # los casts van tras una guarda regex y el componente de rating cae a 0.
    sql, _ = _academy_order()
    assert "case when a.google->>'rating' ~ '^-?[0-9]+(\\.[0-9]+)?$'" in sql
    assert "case when a.google->>'reviews' ~ '^[0-9]+(\\.[0-9]+)?$'" in sql
    assert "end,\n        0\n    )" in sql


def test_simple_orders():
    assert _academy_order("nombre") == (" order by a.name asc", [])
    sql, _ = _academy_order("nuevas")
    assert "a.verified_at desc nulls last" in sql and "a.name asc" in sql


def test_cercanas_uses_haversine_and_repeats_lat():
    sql, params = _academy_order("cercanas", lat=-33.45, lng=-70.66)
    assert "6371" in sql and "radians" in sql and "nulls last" in sql
    assert params == [-33.45, -33.45, -70.66]


def test_invalid_orders_raise():
    with pytest.raises(ValueError):
        _academy_order("cercanas")
    with pytest.raises(ValueError):
        _academy_order("precio")


class _FakeConn:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        return SimpleNamespace(
            fetchall=lambda: self.rows, fetchone=lambda: {"total": len(self.rows)}
        )


def test_list_academies_defaults_to_destacadas():
    conn = _FakeConn()
    list_academies(conn)
    sql, params = conn.calls[-1]
    assert "0.55" in sql and params == (20, 0)


def test_list_academies_appends_coordinates_after_filters():
    conn = _FakeConn()
    list_academies(conn, region="metropolitana", sort="cercanas", lat=-33.45, lng=-70.66)
    sql, params = conn.calls[-1]
    assert "6371" in sql
    assert params == ("metropolitana", -33.45, -33.45, -70.66, 20, 0)
