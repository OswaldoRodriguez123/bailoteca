from types import SimpleNamespace

import pytest

from bailoteca.models import Candidate
from bailoteca.social import parse_followers, run


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2,999 followers · 174 were here", 2999),
        ("1.234 seguidores", 1234),
        ("5.951 seguidores", 5951),
        ("12K followers", 12000),
        ("1.5M followers", 1500000),
        ("Salsa sin números", None),
        (None, None),
    ],
)
def test_parse_followers(text, expected):
    assert parse_followers(text) == expected


class _FakeSource:
    def __init__(self, candidates):
        self.candidates = candidates

    def discover(self):
        return self.candidates


class _FakeConn:
    def __init__(self, academies):
        self.academies = academies
        self.calls = []
        self.updates = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        if "update academies" in sql:
            self.updates.append((sql, tuple(params)))
            return SimpleNamespace(rowcount=1)
        return SimpleNamespace(fetchall=lambda: self.academies)


def test_run_uses_providers_and_skips_missing_numbers():
    queries, conn = [], _FakeConn([{"id": "1", "slug": "a", "name": "Alba"}])

    def factory(query):
        queries.append(query)
        return _FakeSource([
            Candidate(name="x", url="https://x.cl", handle=None, source="brave",
                      raw={"description": "sin datos"}),
            Candidate(name="Alba", url="https://instagram.com/alba", handle="alba",
                      source="brave", raw={"description": "1,043 followers"}),
        ])

    results = run(conn, factory, apply=True)

    assert "social_followers is null" in conn.calls[0][0]
    assert queries == ['"Alba" seguidores instagram']
    assert results[0] == {"slug": "a", "followers": 1043,
                          "network": "instagram", "url": "https://instagram.com/alba"}
    sql, params = conn.updates[0]
    assert params[:2] == (1043, "instagram")


def test_run_dry_run_does_not_write():
    conn = _FakeConn([{"id": "1", "slug": "a", "name": "Alba"}])
    factory = lambda q: _FakeSource([
        Candidate(name="Alba", url="https://facebook.com/alba", handle=None,
                  source="brave", raw={"description": "2,999 followers"})
    ])

    run(conn, factory, apply=False)

    assert conn.updates == []
