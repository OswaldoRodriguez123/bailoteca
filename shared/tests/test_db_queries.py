from bailoteca_shared.db import _academy_filters


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
