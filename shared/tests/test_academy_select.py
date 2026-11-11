from bailoteca_shared import db


def test_academy_select_includes_cover_columns():
    sql = db._ACADEMY_SELECT

    assert "a.cover_url" in sql
    assert "a.cover_source" in sql
    assert "a.cover_fetched_at" in sql
