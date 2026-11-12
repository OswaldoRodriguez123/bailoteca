from types import SimpleNamespace

from bailoteca.backfill_regiones import plan_backfill, run


class _FakeConn:
    """Conexión falsa: la lectura devuelve tuplas y se capturan los updates."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.updates: list[tuple[str, tuple]] = []
        self.commits = 0

    def execute(self, sql, params=None):
        if sql.strip().startswith("select"):
            return SimpleNamespace(fetchall=lambda: list(self._rows))
        if sql.strip().startswith("update"):
            self.updates.append((sql, params))
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"unexpected SQL {sql}")

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_plan_backfill_known_comuna():
    assert plan_backfill([{"id": "1", "comuna": "Santiago"}]) == [
        ("1", "metropolitana")
    ]


def test_plan_backfill_unknown_comuna_is_none():
    assert plan_backfill([{"id": "2", "comuna": "Comuna Fantasma"}]) == [
        ("2", None)
    ]


def test_run_without_apply_does_not_write(capsys):
    conn = _FakeConn([("1", "Santiago"), ("2", "Comuna Fantasma")])

    assert run(conn) == 0

    assert conn.updates == []
    assert conn.commits == 0
    out = capsys.readouterr().out
    assert "total=2" in out
    assert "con_region=1" in out
    assert "sin_match=1" in out
    assert "metropolitana" in out
    assert "Comuna Fantasma" in out


def test_run_apply_updates_matched_rows(capsys):
    conn = _FakeConn(
        [("1", "Santiago"), ("2", "Viña del Mar"), ("3", "Comuna Fantasma")]
    )

    assert run(conn, apply=True) == 0

    assert conn.commits == 1
    assert [params for _, params in conn.updates] == [
        ("metropolitana", "1"),
        ("valparaiso", "2"),
    ]
    out = capsys.readouterr().out
    assert "total=3" in out
    assert "con_region=2" in out
    assert "sin_match=1" in out
    assert "actualizadas=2" in out
