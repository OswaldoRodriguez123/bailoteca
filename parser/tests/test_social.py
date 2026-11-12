import contextlib
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

    @contextlib.contextmanager
    def transaction(self):
        # Savepoint: en la excepción se descartan SOLO las escrituras del bloque.
        marker = len(self.updates)
        try:
            yield
        except Exception:
            del self.updates[marker:]
            raise


class _TxnFakeConn(_FakeConn):
    """UPDATE falla para los ids indicados; el savepoint descarta solo el bloque."""

    def __init__(self, academies, fail_ids):
        super().__init__(academies)
        self.fail_ids = set(fail_ids)

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        if "update academies" in sql:
            if str(params[2]) in self.fail_ids:
                raise RuntimeError("update failed")
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,5M seguidores", 1_500_000),
        ("4,9K seguidores", 4_900),
        ("1,500K seguidores", 1_500_000),
        ("1,234,567 seguidores", 1234567),
        ("1,2345M seguidores", None),
    ],
)
def test_parse_followers_suffix_separators(text, expected):
    assert parse_followers(text) == expected


def test_run_isolates_per_academy_errors():
    conn = _FakeConn([
        {"id": "1", "slug": "a", "name": "Alba"},
        {"id": "2", "slug": "b", "name": "Boka"},
    ])

    class _BoomSource:
        def discover(self):
            raise RuntimeError("boom")

    def factory(query):
        if "Alba" in query:
            return _BoomSource()
        return _FakeSource([
            Candidate(name="Boka", url="https://instagram.com/boka", handle=None,
                      source="brave", raw={"description": "3,210 followers"}),
        ])

    results = run(conn, factory, apply=True)

    assert results[0] == {"slug": "a", "error": "boom"}
    assert results[1] == {"slug": "b", "followers": 3210,
                          "network": "instagram", "url": "https://instagram.com/boka"}
    assert len(conn.updates) == 1


def test_run_update_failure_does_not_double_count_or_abort_following():
    conn = _TxnFakeConn(
        [
            {"id": "1", "slug": "a", "name": "Alba"},
            {"id": "2", "slug": "b", "name": "Boka"},
        ],
        fail_ids={"1"},
    )

    def factory(query):
        name = "Alba" if "Alba" in query else "Boka"
        return _FakeSource([
            Candidate(name=name, url=f"https://instagram.com/{name.lower()}",
                      handle=None, source="brave",
                      raw={"description": "3,210 followers"}),
        ])

    results = run(conn, factory, apply=True)

    errors = [r for r in results if "error" in r]
    written = [r for r in results if "error" not in r]
    assert errors == [{"slug": "a", "error": "update failed"}]
    assert [r["slug"] for r in written] == ["b"]
    assert len(conn.updates) == 1
    assert [params[2] for _, params in conn.updates] == ["2"]


def test_run_update_failure_savepoint_preserves_other_academies():
    conn = _TxnFakeConn(
        [
            {"id": "1", "slug": "a", "name": "Aca"},
            {"id": "2", "slug": "b", "name": "Bob"},
            {"id": "3", "slug": "c", "name": "Cid"},
        ],
        fail_ids={"2"},
    )

    def factory(query):
        name = next(n for n in ("Aca", "Bob", "Cid") if n in query)
        return _FakeSource([
            Candidate(name=name, url=f"https://instagram.com/{name.lower()}",
                      handle=None, source="brave",
                      raw={"description": "3,210 followers"}),
        ])

    results = run(conn, factory, apply=True)

    errors = [r for r in results if "error" in r]
    written = [r for r in results if "error" not in r]
    assert errors == [{"slug": "b", "error": "update failed"}]
    assert [r["slug"] for r in written] == ["a", "c"]
    assert [params[2] for _, params in conn.updates] == ["1", "3"]


def test_run_dry_run_does_not_write():
    conn = _FakeConn([{"id": "1", "slug": "a", "name": "Alba"}])
    factory = lambda q: _FakeSource([
        Candidate(name="Alba", url="https://facebook.com/alba", handle=None,
                  source="brave", raw={"description": "2,999 followers"})
    ])

    run(conn, factory, apply=False)

    assert conn.updates == []
