from types import SimpleNamespace

from bailoteca_shared.db import _academy_filters, list_comunas


def test_no_filters_returns_empty_where():
    where, params = _academy_filters()
    assert where == ""
    assert params == []


def test_comuna_filter_is_case_insensitive():
    where, params = _academy_filters(comuna="Providencia")
    assert "lower(al.comuna) = lower(%s)" in where
    assert params == ["Providencia"]


def test_style_filter_uses_slug():
    where, params = _academy_filters(style="salsa-cubana")
    assert "s.slug = %s" in where
    assert params == ["salsa-cubana"]


def test_q_filter_searches_name_and_description():
    where, params = _academy_filters(q="danson")
    assert "a.name ilike %s" in where
    assert "coalesce(a.description, '') ilike %s" in where
    assert params == ["%danson%", "%danson%"]


def test_q_filter_escapes_like_wildcards():
    _, params = _academy_filters(q="100%_")
    assert params == ["%100\\%\\_%", "%100\\%\\_%"]


def test_q_filter_escapes_backslash():
    _, params = _academy_filters(q="a\\b")
    assert params == ["%a\\\\b%", "%a\\\\b%"]


def test_combined_filters_are_anded_in_order():
    where, params = _academy_filters(
        comuna="Santiago", style="mambo", q="baile"
    )
    assert where.startswith(" where ")
    assert where.index("al.comuna") < where.index("s.slug") < where.index("ilike")
    assert params == ["Santiago", "mambo", "%baile%", "%baile%"]


def test_region_filter_is_null_tolerant():
    where, params = _academy_filters(region="metropolitana")
    assert "al.region = %s or al.region is null" in where
    assert params == ["metropolitana"]


def test_region_all_is_ignored():
    where, params = _academy_filters(region="all")
    assert where == ""
    assert params == []


def test_region_filter_appended_after_other_filters():
    where, params = _academy_filters(
        comuna="Providencia", style="mambo", q="baile", region="valparaiso"
    )
    assert where.index("al.comuna") < where.index("s.slug") < where.index("ilike")
    assert where.index("ilike") < where.index("al.region")
    assert params == [
        "Providencia",
        "mambo",
        "%baile%",
        "%baile%",
        "valparaiso",
    ]


class _FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, tuple(params)))
        return SimpleNamespace(fetchall=lambda: self.rows)


def test_list_comunas_with_region_is_null_tolerant():
    conn = _FakeConn([{"comuna": "Ñuñoa"}])

    comunas = list_comunas(conn, region="metropolitana")

    sql, params = conn.calls[0]
    assert "region = %s or region is null" in sql
    assert params == ("metropolitana",)
    assert comunas == ["Ñuñoa"]


def test_list_comunas_all_omits_region_clause():
    conn = _FakeConn([{"comuna": "Santiago"}])

    comunas = list_comunas(conn, region="all")

    sql, params = conn.calls[0]
    assert "region" not in sql
    assert params == ()
    assert comunas == ["Santiago"]


def test_list_comunas_without_region_omits_region_clause():
    conn = _FakeConn([{"comuna": "Santiago"}])

    comunas = list_comunas(conn)

    sql, params = conn.calls[0]
    assert "region" not in sql
    assert params == ()
    assert comunas == ["Santiago"]
